"""SQLAlchemy models for the Cosmetics POS."""
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, event, func
from sqlalchemy.orm import Mapped, Session, declared_attr, mapped_column, relationship, with_loader_criteria

from database import Base


class UserRole(str, PyEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    CASHIER = "cashier"


class SaleStatus(str, PyEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    VOIDED = "voided"
    REFUNDED = "refunded"


class PaymentMethod(str, PyEnum):
    CASH = "cash"
    MPESA = "mpesa"
    CARD = "card"
    CREDIT = "credit"


class POStatus(str, PyEnum):
    DRAFT = "draft"
    SENT = "sent"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class AlertType(str, PyEnum):
    LOW_STOCK = "low_stock"
    EXPIRY = "expiry"
    OUT_OF_STOCK = "out_of_stock"


class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class TenantOwned:
    @declared_attr
    def business_id(cls):
        return Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)


@event.listens_for(Session, "do_orm_execute")
def _scope_tenant_queries(execute_state):
    business_id = execute_state.session.info.get("business_id")
    if business_id is not None and execute_state.is_select:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                TenantOwned,
                lambda model: model.business_id == business_id,
                include_aliases=True,
            )
        )


@event.listens_for(Session, "before_flush")
def _assign_tenant_to_new_rows(session, _flush_context, _instances):
    business_id = session.info.get("business_id")
    for instance in session.new:
        if isinstance(instance, TenantOwned):
            row_business_id = instance.business_id
            if row_business_id is None and instance.__tablename__ in {
                "audit_logs",
                "mpesa_transactions",
            }:
                continue
            if row_business_id is None and business_id is not None:
                instance.business_id = business_id
            elif row_business_id is None:
                raise ValueError(
                    f"{type(instance).__name__} must be assigned to a business"
                )
            elif business_id is not None and row_business_id != business_id:
                raise ValueError("Cannot create a record for another business")


class User(TenantOwned, Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CASHIER)
    is_active = Column(Boolean, default=True, nullable=False)
    phone = Column(String(20), nullable=True)
    sms_tokens = Column(Integer, default=0, server_default="0", nullable=False)
    business_name = Column(String(200), nullable=True)
    created_at = Column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime, nullable=True)
    sales = relationship("Sale", foreign_keys="[Sale.cashier_id]", back_populates="cashier")
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(TenantOwned, Base):
    __tablename__ = "audit_logs"
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, index=True)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=True)
    entity_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    user = relationship("User", back_populates="audit_logs")


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    user = relationship("User")


class Supplier(TenantOwned, Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    contact_name = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")
    inventory_items = relationship("Inventory", back_populates="supplier")
    __table_args__ = (
        Index("uq_suppliers_business_name", "business_id", "name", unique=True),
    )


class Product(TenantOwned, Base):
    """Cosmetics product catalogue. Only cosmetics-relevant fields remain."""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False, index=True)
    brand_name = Column(String(300), nullable=True)
    variant = Column(String(200), nullable=True)  # shade, size, scent, etc.
    barcode = Column(String(100), nullable=True)
    manufacturer = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(80), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    reorder_level = Column(Integer, default=10, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    source = Column(String(50), default="manual")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    inventory = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    sale_items = relationship("SaleItem", back_populates="product")
    po_items = relationship("POItem", back_populates="product")
    alerts = relationship("ProductAlert", back_populates="product", cascade="all, delete-orphan")
    __table_args__ = (
        Index("ix_products_name_brand", "name", "brand_name"),
        Index("uq_products_business_barcode", "business_id", "barcode", unique=True),
    )


class Inventory(TenantOwned, Base):
    """Stock records for products. Multiple receipts may exist for one product."""
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    batch_number = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False, default=0)
    unit_cost = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    selling_price = Column(Numeric(10, 2), nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    received_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)
    product = relationship("Product", back_populates="inventory")
    supplier = relationship("Supplier", back_populates="inventory_items")
    __table_args__ = (Index("ix_inventory_expires", "expires_at", "product_id"),)


class Customer(TenantOwned, Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    loyalty_points = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    sales = relationship("Sale", back_populates="customer")
    __table_args__ = (
        Index("uq_customers_business_phone", "business_id", "phone", unique=True),
    )


class Sale(TenantOwned, Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    receipt_number = Column(String(50), nullable=False)
    cashier_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    subtotal = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    discount_amount = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    amount_paid = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    change_given = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    payment_method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.CASH)
    status = Column(Enum(SaleStatus), nullable=False, default=SaleStatus.PENDING)
    notes = Column(Text, nullable=True)
    sold_at = Column(DateTime, server_default=func.now(), index=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    void_reason = Column(Text, nullable=True)
    cashier = relationship("User", foreign_keys="[Sale.cashier_id]", back_populates="sales")
    voided_by = relationship("User", foreign_keys="[Sale.voided_by_id]")
    customer = relationship("Customer", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    mpesa_transactions = relationship("MpesaTransaction", back_populates="sale")
    __table_args__ = (
        Index("ix_sales_sold_at_status", "sold_at", "status"),
        Index("uq_sales_business_receipt_number", "business_id", "receipt_number", unique=True),
    )


class SaleItem(TenantOwned, Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    inventory_id = Column(Integer, ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount_pct = Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    line_total = Column(Numeric(10, 2), nullable=False)
    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")


class PurchaseOrder(TenantOwned, Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String(50), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    raised_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum(POStatus), nullable=False, default=POStatus.DRAFT)
    total_amount = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    notes = Column(Text, nullable=True)
    ordered_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    supplier = relationship("Supplier", back_populates="purchase_orders")
    raised_by = relationship("User", foreign_keys="[PurchaseOrder.raised_by_id]")
    items = relationship("POItem", back_populates="purchase_order", cascade="all, delete-orphan")
    __table_args__ = (
        Index("uq_purchase_orders_business_po_number", "business_id", "po_number", unique=True),
    )


class POItem(TenantOwned, Base):
    __tablename__ = "po_items"
    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity_ordered = Column(Integer, nullable=False)
    quantity_received = Column(Integer, nullable=False, default=0)
    unit_cost = Column(Numeric(10, 2), nullable=False)
    line_total = Column(Numeric(10, 2), nullable=False)
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product", back_populates="po_items")


class ProductAlert(TenantOwned, Base):
    __tablename__ = "product_alerts"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    message = Column(Text, nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    product = relationship("Product", back_populates="alerts")
    resolved_by = relationship("User", foreign_keys="[ProductAlert.resolved_by_id]")


class MpesaStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MpesaTransaction(TenantOwned, Base):
    __tablename__ = "mpesa_transactions"
    business_id: Mapped[Optional[int]] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sales.id"), nullable=True, index=True)
    checkout_request_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    merchant_request_id: Mapped[str] = mapped_column(String(100))
    phone_number: Mapped[str] = mapped_column(String(15))
    amount: Mapped[int] = mapped_column(Integer)
    mpesa_receipt: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    result_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_desc: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[MpesaStatus] = mapped_column(Enum(MpesaStatus), default=MpesaStatus.PENDING)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    registration_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pending_full_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    pending_business_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pending_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pending_password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pending_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    purpose: Mapped[str] = mapped_column(String(30), default="sale")
    sale = relationship("Sale", back_populates="mpesa_transactions")
