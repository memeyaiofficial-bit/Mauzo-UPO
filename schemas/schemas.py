"""Pydantic schemas for the Cosmetics POS."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from models.orm import AlertType, PaymentMethod, POStatus, SaleStatus, UserRole, MpesaStatus

class _OrmBase(BaseModel):
    model_config = {"from_attributes": True}

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
class TokenRefreshIn(BaseModel): refresh_token: str
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

class UserBase(_OrmBase):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: UserRole = UserRole.CASHIER
    phone: Optional[str] = None
class UserCreateIn(UserBase):
    password: str = Field(min_length=8, max_length=128)
    @field_validator("password")
    @classmethod
    def password_complexity(cls, v):
        if not any(c.isupper() for c in v) or not any(c.islower() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain uppercase, lowercase and a digit")
        return v
class UserUpdateIn(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
class ForgotPasswordIn(BaseModel): email: str
class ResetPasswordIn(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)

# PRODUCTS
class ProductBase(_OrmBase):
    name: str = Field(min_length=1, max_length=300)
    brand_name: Optional[str] = None
    variant: Optional[str] = None
    barcode: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    reorder_level: int = Field(default=10, ge=0)
    unit_price: Decimal = Field(ge=Decimal("0.00"))
    initial_stock: int = Field(default=0, ge=0)

class ProductCreateIn(ProductBase):
    initial_unit_cost: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    initial_supplier_id: Optional[int] = None
    initial_batch_number: Optional[str] = None
    initial_expires_at: Optional[datetime] = None

class ProductUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    brand_name: Optional[str] = None
    variant: Optional[str] = None
    barcode: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    unit_price: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"))
    reorder_level: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None

class ProductOut(ProductBase):
    id: int
    is_active: bool
    source: str
    created_at: datetime
    updated_at: Optional[datetime] = None

class ProductSearchOut(BaseModel):
    id: int
    name: str
    brand_name: Optional[str]
    variant: Optional[str]
    barcode: Optional[str]
    unit_price: Decimal
    is_active: bool
    reorder_level: int
    category: Optional[str] = None
    model_config = {"from_attributes": True}

# INVENTORY
class InventoryCreateIn(BaseModel):
    product_id: int
    supplier_id: Optional[int] = None
    batch_number: Optional[str] = None
    quantity: int = Field(ge=1)
    unit_cost: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    selling_price: Decimal = Field(ge=Decimal("0.00"))
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
class InventoryUpdateIn(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=0)
    selling_price: Optional[Decimal] = Field(default=None, ge=Decimal("0.00"))
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
class InventoryOut(_OrmBase):
    id: int
    product_id: int
    supplier_id: Optional[int]
    batch_number: Optional[str]
    quantity: int
    unit_cost: Decimal
    selling_price: Decimal
    expires_at: Optional[datetime]
    received_at: datetime
class InventorySummaryOut(BaseModel):
    product_id: int
    product_name: str
    total_quantity: int
    lowest_selling_price: Optional[Decimal]
    earliest_expiry: Optional[datetime]

# SALES
class SaleItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)
    discount_pct: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
class SaleCreateIn(BaseModel):
    customer_id: Optional[int] = None
    items: List[SaleItemIn] = Field(min_length=1)
    payment_method: PaymentMethod = PaymentMethod.CASH
    amount_paid: Decimal = Field(ge=Decimal("0.00"))
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    notes: Optional[str] = None
    mpesa_receipt: Optional[str] = None
class SaleItemOut(_OrmBase):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    discount_pct: Decimal
    line_total: Decimal
class SaleOut(_OrmBase):
    id: int
    receipt_number: str
    cashier_id: Optional[int]
    customer_id: Optional[int]
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    change_given: Decimal
    payment_method: PaymentMethod
    status: SaleStatus
    notes: Optional[str]
    sold_at: datetime
    items: List[SaleItemOut] = []
class VoidSaleIn(BaseModel): reason: str = Field(min_length=5, max_length=500)

# SUPPLIERS
class SupplierBase(_OrmBase):
    name: str = Field(min_length=2, max_length=200)
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
class SupplierCreateIn(SupplierBase): pass
class SupplierUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None
class SupplierOut(SupplierBase):
    id: int
    is_active: bool
    created_at: datetime

# CUSTOMERS
class CustomerCreateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
class CustomerUpdateIn(CustomerCreateIn):
    is_active: Optional[bool] = None
class CustomerOut(CustomerCreateIn):
    id: int
    loyalty_points: int
    is_active: bool
    created_at: datetime

# PURCHASE ORDERS
class POItemIn(BaseModel):
    product_id: int
    quantity_ordered: int = Field(ge=1)
    unit_cost: Decimal = Field(ge=0)
class PurchaseOrderCreateIn(BaseModel):
    supplier_id: int
    items: List[POItemIn] = Field(min_length=1)
    notes: Optional[str] = None
class POItemOut(_OrmBase):
    id: int
    product_id: int
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal
    line_total: Decimal
class PurchaseOrderOut(_OrmBase):
    id: int
    po_number: str
    supplier_id: int
    raised_by_id: Optional[int]
    status: POStatus
    total_amount: Decimal
    notes: Optional[str]
    ordered_at: Optional[datetime]
    received_at: Optional[datetime]
    created_at: datetime
    items: List[POItemOut] = []

# ALERTS
class AlertOut(_OrmBase):
    id: int
    product_id: int
    alert_type: AlertType
    message: str
    is_resolved: bool
    resolved_by_id: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime

# REPORTS
class SalesSummaryOut(BaseModel):
    period: str
    total_sales: int
    total_revenue: Decimal
    total_discount: Decimal
    total_tax: Decimal
    net_revenue: Decimal
class TopProductOut(BaseModel):
    product_id: int
    product_name: str
    total_quantity_sold: int
    total_revenue: Decimal
class DashboardOut(BaseModel):
    total_products: int
    active_products: int
    low_stock_count: int
    expiring_soon_count: int
    todays_sales_count: int
    todays_revenue: Decimal
    pending_purchase_orders: int
    unresolved_alerts: int

# M-PESA
class MpesaSTKPushIn(BaseModel):
    sale_id: int
    phone_number: str
class MpesaSTKPushOut(BaseModel):
    checkout_request_id: str
    message: str
class MpesaStatusOut(BaseModel):
    status: MpesaStatus
    result_desc: Optional[str] = None
class RegisterInitiateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    business_name: str = Field(min_length=2, max_length=200)
    email: str
    password: str = Field(min_length=8, max_length=128)
    phone_number: str
class RegisterInitiateOut(BaseModel):
    checkout_request_id: str
    amount: int
    message: str
