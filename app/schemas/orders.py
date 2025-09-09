from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class CartItem(BaseModel):
    id: str
    name: str
    price: float
    quantity: int
    image_url: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None

class AddressSchema(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    phone: str = Field(..., min_length=10, max_length=20)
    address: str = Field(..., min_length=5, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., min_length=3, max_length=20)
    country: str = Field(..., min_length=2, max_length=100)

class CreateOrderRequest(BaseModel):
    items: List[CartItem]
    total_amount: float = Field(..., gt=0)
    shipping_address: AddressSchema
    billing_address: Optional[AddressSchema] = None
    shipping_cost: Optional[float] = Field(0, ge=0)
    tax_amount: Optional[float] = Field(0, ge=0)
    discount_amount: Optional[float] = Field(0, ge=0)
    notes: Optional[str] = Field(None, max_length=500)
    shipping_method: Optional[str] = Field(None, max_length=100)
    order_number: Optional[str] = Field(None, max_length=50)

class OrderUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, pattern=r"^(pending|confirmed|processing|shipped|delivered|cancelled)$")
    payment_status: Optional[str] = Field(None, pattern=r"^(pending|paid|failed|refunded)$")
    tracking_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)

class OrderItemResponse(BaseModel):
    id: UUID
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    product_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    items: List[CartItem]
    total_amount: float
    shipping_address: AddressSchema
    billing_address: Optional[AddressSchema] = None
    status: str
    payment_status: str
    stripe_session_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    notes: Optional[str] = None
    tracking_number: Optional[str] = None
    shipping_method: Optional[str] = None
    shipping_cost: float
    tax_amount: float
    discount_amount: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrderListResponse(BaseModel):
    orders: List[OrderResponse]
    total: int
    skip: int
    limit: int

class OrderStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(pending|confirmed|processing|shipped|delivered|cancelled)$")

class PaymentStatusUpdate(BaseModel):
    payment_status: str = Field(..., pattern=r"^(pending|paid|failed|refunded)$")
    stripe_session_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
