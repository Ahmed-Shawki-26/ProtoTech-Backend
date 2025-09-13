# app/database/new_models.py
# New database models migrated from proto_tech3-main

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, JSON, Float, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .core import Base

# Enums for order and payment status
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

# Order model for general e-commerce orders
class Order(Base):
    __tablename__ = 'orders'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    order_number = Column(String, unique=True, nullable=False)
    
    # Money stored as Integer (in cents/piastres) to avoid float precision issues
    total_amount = Column(Integer, nullable=False)  # e.g., 150.50 EGP is stored as 15050
    shipping_cost = Column(Integer, nullable=False, default=0)
    tax_amount = Column(Integer, nullable=False, default=0)
    discount_amount = Column(Integer, nullable=False, default=0)

    # Addresses stored as JSON for flexibility
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
    
    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user = relationship("User", back_populates="orders")

    def __repr__(self):
        return f"<Order(order_number='{self.order_number}', status='{self.status}')>"

# OrderItem model for individual items within orders
class OrderItem(Base):
    __tablename__ = 'order_items'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id'), nullable=False, index=True)
    
    product_id = Column(String, nullable=False)  # Odoo product ID
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    
    # Money stored as Integer (in cents/piastres)
    unit_price = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    
    product_data = Column(JSON, nullable=True)  # For storing extra details like color, options, etc.
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="items")

    def __repr__(self):
        return f"<OrderItem(product_name='{self.product_name}', quantity={self.quantity})>"

# PCB Order model for PCB manufacturing orders
class PcbOrder(Base):
    __tablename__ = 'pcb_orders'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core order information
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    order_number = Column(String, unique=True, nullable=False, index=True)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    
    # Information determined from the Gerber file
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    
    # Price and payment information
    final_price_egp = Column(Float, nullable=False)
    stripe_payment_intent_id = Column(String, nullable=True, index=True)
    
    # Manufacturing parameters
    base_material = Column(String, nullable=False)  # Top-level field for easy filtering
    manufacturing_parameters = Column(JSON, nullable=False)  # Flexible JSONB column for all parameters
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<PcbOrder(order_number='{self.order_number}', material='{self.base_material}', status='{self.status}')>"

# User Cart model for persistent shopping carts
class UserCart(Base):
    __tablename__ = 'user_carts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Unique ensures a one-to-one relationship with the user
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, unique=True)
    
    # Storing cart items as a JSON array of objects is very flexible
    items = Column(JSON, nullable=False, server_default='[]')
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cart")

    def __repr__(self):
        return f"<UserCart(user_id='{self.user_id}', items_count={len(self.items) if self.items else 0})>"
