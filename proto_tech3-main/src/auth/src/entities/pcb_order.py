# /src/auth/entities/pcb_order.py

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, JSON, Float, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database.core import Base
import enum

# We can reuse the OrderStatus from the main order entity if they share statuses
from .order import OrderStatus

class PcbOrder(Base):
    __tablename__ = 'pcb_orders'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # --- Core Order Information ---
    # This can be linked to a main `orders` table if a PCB order is part of a larger order.
    # For now, we'll link it directly to the user.
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    order_number = Column(String, unique=True, nullable=False, index=True)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    
    # --- Information determined from the Gerber file ---
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    
    # --- Price and Payment Information ---
    final_price_egp = Column(Float, nullable=False)
    stripe_payment_intent_id = Column(String, nullable=True, index=True)
    
    # --- Manufacturing Parameters ---
    # The 'base_material' is a top-level field for easy filtering.
    base_material = Column(String, nullable=False)
    
    # A JSONB column is perfect for storing all the varying parameters.
    # It's flexible, indexable, and efficient in PostgreSQL.
    manufacturing_parameters = Column(JSON, nullable=False)
    
    # --- Timestamps ---
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    user = relationship("User")