# /src/auth/entities/user_cart.py

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.schema import FetchedValue

from ..database.core import Base

class UserCart(Base):
    __tablename__ = 'user_carts'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Unique ensures a one-to-one relationship with the user
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, unique=True)
    
    # Storing cart items as a JSON array of objects is very flexible
    items = Column(JSON, nullable=False, server_default='[]')
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    user = relationship("User", back_populates="cart")