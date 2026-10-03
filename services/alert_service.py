"""
services/alert_service.py
──────────────────────────
Generates and manages product alerts (low stock, expiry).

This service is called:
  • After every sale (to check if stock dropped below reorder level).
  • On a scheduled basis via the /admin/alerts/scan endpoint.
  • On startup (after DB init).

RISKS MITIGATED:
  • Duplicate alert prevention → one active alert per product per type.
  • Expiry window configurable (default 30 days) → manager can tune.
  • Alerts reference product_id not name → safe after renames.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session
from models.orm import AuditLog

from models.orm import AlertType, Inventory, Product, ProductAlert

logger = logging.getLogger(__name__)

EXPIRY_WARNING_DAYS = 30  # Flag products expiring within this many days


def _has_active_alert(db: Session, product_id: int, alert_type: AlertType) -> bool:
    """Return True if an unresolved alert of this type already exists."""
    return (
        db.query(ProductAlert)
        .filter(
            ProductAlert.product_id == product_id,
            ProductAlert.alert_type == alert_type,
            ProductAlert.is_resolved == False,
        )
        .first()
    ) is not None


def check_stock_alerts(db: Session, product_id: int) -> None:
    """
    Check stock level for one product and create alert if needed.
    Called after every sale transaction.
    """
    product = db.get(Product, product_id)
    if not product or not product.is_active:
        return

    total_qty = (
        db.query(func.sum(Inventory.quantity))
        .filter(Inventory.product_id == product_id)
        .scalar()
    ) or 0

    if total_qty == 0:
        alert_type = AlertType.OUT_OF_STOCK
        message = f"'{product.name}' is completely out of stock."
        # Auto-resolve any existing LOW_STOCK alert so the worse alert is visible
        _resolve_superseded_alert(db, product_id, AlertType.LOW_STOCK)
    elif total_qty <= product.reorder_level:
        alert_type = AlertType.LOW_STOCK
        message = (
            f"'{product.name}' stock is low: {total_qty} units remaining "
            f"(reorder level: {product.reorder_level})."
        )
    else:
        # Stock is fine — auto-resolve any open stock alerts
        _resolve_superseded_alert(db, product_id, AlertType.LOW_STOCK)
        _resolve_superseded_alert(db, product_id, AlertType.OUT_OF_STOCK)
        return  # Stock is fine

    if not _has_active_alert(db, product_id, alert_type):
        db.add(ProductAlert(
            product_id=product_id,
            alert_type=alert_type,
            message=message,
        ))
        db.commit()
        logger.info("Alert created: %s for product_id=%d", alert_type, product_id)

def _resolve_superseded_alert(db: Session, product_id: int, alert_type: AlertType) -> None:
    """Silently resolve an alert that has been superseded by a more severe one."""
    alert = (
        db.query(ProductAlert)
        .filter(
            ProductAlert.product_id == product_id,
            ProductAlert.alert_type == alert_type,
            ProductAlert.is_resolved == False,
        )
        .first()
    )
    if alert:
        alert.is_resolved = True
        alert.resolved_at = datetime.now(timezone.utc)
        # resolved_by_id stays None — indicates system auto-resolution


def scan_expiry_alerts(db: Session) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=EXPIRY_WARNING_DAYS)
    """
    Scan all inventory batches for products expiring within EXPIRY_WARNING_DAYS.
    Returns count of new alerts created.
    """
    now_naive = now.replace(tzinfo=None)
    cutoff_naive = cutoff.replace(tzinfo=None)

    expiring_batches = (
        db.query(Inventory)
        .filter(
            Inventory.expires_at <= cutoff_naive,
            Inventory.expires_at >= now_naive,
            Inventory.quantity > 0,
        )
        .all()
    )


    new_alerts = 0
    for batch in expiring_batches:
        product = db.get(Product, batch.product_id)
        if product is None:
            logger.warning(
                "Inventory batch id=%d references non-existent product_id=%d — skipping.",
                batch.id, batch.product_id,
            )
            continue  # Skip this batch entirely; don't insert a broken alert

        if not _has_active_alert(db, batch.product_id, AlertType.EXPIRY):
            expires_aware = (
                batch.expires_at.replace(tzinfo=timezone.utc)
                if batch.expires_at.tzinfo is None
                else batch.expires_at
            )
            days_left = (expires_aware - datetime.now(timezone.utc)).days

            db.add(ProductAlert(
                product_id=batch.product_id,
                alert_type=AlertType.EXPIRY,
                message=(
                    f"Batch '{batch.batch_number or 'N/A'}' of "
                    f"'{product.name if product else 'Unknown'}' "
                    f"expires in {days_left} day(s) "
                    f"({batch.expires_at.strftime('%Y-%m-%d')}). "
                    f"Quantity: {batch.quantity}."
                ),
            ))
            new_alerts += 1

    if new_alerts:
        db.commit()
        logger.info("Expiry scan: %d new alert(s) created", new_alerts)
    return new_alerts


def resolve_alert(db: Session, alert_id: int, user_id: int) -> ProductAlert:
    """Mark an alert as resolved."""
    alert = db.get(ProductAlert, alert_id)
    if not alert:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.is_resolved = True
    alert.resolved_by_id = user_id
    alert.resolved_at = datetime.now(timezone.utc)
    db.add(AuditLog(
        user_id=user_id,
        action="ALERT_RESOLVED",
        entity="ProductAlert",
        entity_id=alert_id,
        detail=f"Alert type={alert.alert_type} resolved for product_id={alert.product_id}",
    ))
    db.commit()
    db.refresh(alert)
    return alert