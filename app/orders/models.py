from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database.core import Base
import uuid
from datetime import datetime

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_number = Column(String, unique=True, nullable=False)
    # Store cart items snapshot as JSON for denormalized record keeping
    cart_items = Column(JSON, nullable=False)  # Renamed from 'items' to avoid conflict
    total_amount = Column(Float, nullable=False)
    shipping_address = Column(JSON, nullable=False)
    billing_address = Column(JSON, nullable=True)
    status = Column(String, default="pending")  # pending, confirmed, processing, shipped, delivered, cancelled
    payment_status = Column(String, default="pending")  # pending, paid, failed, refunded
    stripe_session_id = Column(String, nullable=True)
    stripe_payment_intent_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    tracking_number = Column(String, nullable=True)
    shipping_method = Column(String, nullable=True)
    shipping_cost = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - Temporarily removed back_populates to fix circular imports
    user = relationship("User")
    # Name the child relationship something other than `items` to avoid
    # clashing with the JSON column above.
    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, nullable=False)  # Odoo product ID
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    product_data = Column(JSON, nullable=True)  # Store additional product info
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="order_items")
