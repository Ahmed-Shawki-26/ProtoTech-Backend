# app/pcb_orders/models.py
# New PCB Order model for PCB manufacturing orders

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database.core import Base

# Enum for PCB order status (reusing the same values as regular orders)
class PcbOrderStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
    FAILED = "failed"

class PcbOrder(Base):
    """
    PCB Order model for PCB manufacturing orders.
    This is a specialized order type for PCB manufacturing with specific fields.
    """
    __tablename__ = 'pcb_orders'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core order information
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    order_number = Column(String, unique=True, nullable=False, index=True)
    status = Column(Enum(PcbOrderStatus), nullable=False, default=PcbOrderStatus.PENDING)
    
    # Information determined from the Gerber file
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    
    # Price and payment information
    final_price_egp = Column(Float, nullable=False)
    stripe_payment_intent_id = Column(String, nullable=True, index=True)
    
    # Manufacturing parameters
    base_material = Column(String, nullable=False)  # Top-level field for easy filtering
    manufacturing_parameters = Column(JSON, nullable=False)  # Flexible JSON column for all parameters
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<PcbOrder(order_number='{self.order_number}', material='{self.base_material}', status='{self.status}')>"
    
    @property
    def area_cm2(self):
        """Calculate PCB area in cm²"""
        return (self.width_mm * self.height_mm) / 100.0
    
    @property
    def area_m2(self):
        """Calculate PCB area in m²"""
        return (self.width_mm * self.height_mm) / 1000000.0
    
    def get_manufacturing_param(self, param_name, default=None):
        """Safely get a manufacturing parameter"""
        if self.manufacturing_parameters and isinstance(self.manufacturing_parameters, dict):
            return self.manufacturing_parameters.get(param_name, default)
        return default
    
    def set_manufacturing_param(self, param_name, value):
        """Safely set a manufacturing parameter"""
        if not self.manufacturing_parameters:
            self.manufacturing_parameters = {}
        if isinstance(self.manufacturing_parameters, dict):
            self.manufacturing_parameters[param_name] = value
