# src/entities/user.py

from sqlalchemy import Column, String, Boolean, Index, DateTime # <--- Add DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from ..database.core import Base
from datetime import datetime, timezone # <--- Add timezone
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional

class User(Base):
    """
    SQLAlchemy model representing a user in the database.
    """
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    auth_provider = Column(String, nullable=False, default='email')
    # --- NEW: Add created_at column ---
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    # Default shipping address fields
    default_company = Column(String, nullable=True)
    default_country = Column(String, nullable=True)
    default_address_line1 = Column(String, nullable=True)
    default_address_line2 = Column(String, nullable=True)
    default_city = Column(String, nullable=True)
    default_state = Column(String, nullable=True)
    default_zip_code = Column(String, nullable=True)
    default_phone_number = Column(String, nullable=True)

    # Relationships - Temporarily removed to fix authentication endpoint
    # These will be restored once the circular import issues are resolved
    # orders = relationship("Order", back_populates="user", lazy="select")
    # cart = relationship("UserCart", back_populates="user", uselist=False, lazy="select")

    def __repr__(self):
        """String representation of the User object."""
        return f"<User(email='{self.email}', first_name='{self.first_name}', last_name='{self.last_name}')>"


# Pydantic schemas for shipping address operations
class ShippingAddressUpdate(BaseModel):
    """Schema for updating user's default shipping address"""
    company: Optional[str] = None
    country: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ShippingAddressResponse(BaseModel):
    """Schema for returning user's default shipping address"""
    company: Optional[str] = None
    country: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)