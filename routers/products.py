"""Product catalogue endpoints for the Cosmetics POS."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from database import get_db
from models.orm import AuditLog, Inventory, Product, User
from schemas.schemas import ProductCreateIn, ProductOut, ProductSearchOut, ProductUpdateIn
from utils.security import get_current_user, require_admin, require_admin_or_manager

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("", response_model=list[ProductSearchOut])
def search_products(q: str = Query(None), is_active: bool = Query(True), category: str = Query(None), skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=3000), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Product)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    if category:
        query = query.filter(Product.category == category)
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(pattern), Product.brand_name.ilike(pattern), Product.variant.ilike(pattern), Product.barcode.ilike(pattern), Product.category.ilike(pattern)))
    return query.order_by(Product.name).offset(skip).limit(limit).all()

@router.get("/meta/categories", response_model=list[str])
def list_categories(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Product.category).filter(Product.category.isnot(None), Product.category != "").distinct().order_by(Product.category).all()
    return [r[0] for r in rows]

@router.get("/barcode/{barcode}", response_model=ProductOut)
def get_by_barcode(barcode: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.barcode == barcode, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"No product found with barcode '{barcode}'")
    return product

@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreateIn, current_user: User = Depends(require_admin_or_manager), db: Session = Depends(get_db)):
    if payload.barcode:
        existing = db.query(Product).filter(Product.barcode == payload.barcode).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Product with barcode '{payload.barcode}' already exists")
    if payload.initial_supplier_id:
        from models.orm import Supplier
        supplier = db.get(Supplier, payload.initial_supplier_id)
        if not supplier or not supplier.is_active:
            raise HTTPException(status_code=404, detail="Initial supplier not found or inactive")
    product = Product(
        name=payload.name.strip(), brand_name=payload.brand_name, variant=payload.variant,
        barcode=payload.barcode, manufacturer=payload.manufacturer, description=payload.description,
        category=payload.category, reorder_level=payload.reorder_level,
        unit_price=payload.unit_price, source="manual", is_active=True,
    )
    db.add(product)
    db.flush()
    if payload.initial_stock > 0:
        db.add(Inventory(
            product_id=product.id,
            supplier_id=payload.initial_supplier_id,
            batch_number=payload.initial_batch_number,
            quantity=payload.initial_stock,
            unit_cost=payload.initial_unit_cost,
            selling_price=payload.unit_price,
            expires_at=payload.initial_expires_at,
            notes="Initial stock entered during product creation",
        ))
    db.add(AuditLog(user_id=current_user.id, action="PRODUCT_CREATED", entity="Product", entity_id=product.id,
                    detail=f"Created product '{product.name}' with initial stock={payload.initial_stock}"))
    db.commit(); db.refresh(product)
    return product

@router.patch("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductUpdateIn, current_user: User = Depends(require_admin_or_manager), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    changes = payload.model_dump(exclude_none=True)
    if changes.get("barcode"):
        dup = db.query(Product).filter(Product.barcode == changes["barcode"], Product.id != product_id).first()
        if dup:
            raise HTTPException(status_code=409, detail="That barcode belongs to another product")
    for field, value in changes.items(): setattr(product, field, value)
    if "unit_price" in changes:
        # New sales use the product price; existing stock rows keep their historical price snapshot.
        pass
    db.add(AuditLog(user_id=current_user.id, action="PRODUCT_UPDATED", entity="Product", entity_id=product.id,
                    detail=f"Updated fields: {list(changes.keys())}"))
    db.commit(); db.refresh(product)
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_product(product_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    db.add(AuditLog(user_id=current_user.id, action="PRODUCT_DEACTIVATED", entity="Product", entity_id=product.id,
                    detail=f"Deactivated product '{product.name}'"))
    db.commit()
