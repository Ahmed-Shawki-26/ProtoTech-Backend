# /src/auth/entities/order.py

import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, JSON, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database.core import Base

# Using Enums is a best practice for status fields
class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
    FAILED = "failed"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

class Order(Base):
    __tablename__ = 'orders'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    order_number = Column(String, unique=True, nullable=False)
    
    # It's better to store money as an Integer (in cents/piastres) to avoid float precision issues.
    # We will assume your application logic will handle the conversion.
    total_amount = Column(Integer, nullable=False) # e.g., 150.50 EGP is stored as 15050
    shipping_cost = Column(Integer, nullable=False, default=0)
    tax_amount = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)

    # Storing addresses as JSON is flexible
    shipping_address = Column(JSON, nullable=False)
    billing_address = Column(JSON, nullable=True)

    # Status fields using Enums
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    payment_status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)

    # Tracking and integration fields
    stripe_session_id = Column(String, nullable=True, index=True)
    stripe_payment_intent_id = Column(String, nullable=True, index=True)
    tracking_number = Column(String, nullable=True)
    shipping_method = Column(String, nullable=True)
    
    notes = Column(Text, nullable=True)
    
    # Timestamps with server defaults
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user = relationship("User", back_populates="orders")

class OrderItem(Base):
    __tablename__ = 'order_items'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id'), nullable=False, index=True)
    
    product_id = Column(String, nullable=False) # Odoo product ID
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    
    # Storing money as Integer (in cents/piastres)
    unit_price = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    
    product_data = Column(JSON, nullable=True) # For storing extra details like color, options, etc.
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # --- Relationships ---
    order = relationship("Order", back_populates="items")