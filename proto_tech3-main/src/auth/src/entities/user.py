# /src/auth/entities/user.py

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database.core import Base

class User(Base):
    """
    SQLAlchemy model representing a user in the database.
    """
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=True) # Nullable for social logins
    is_verified = Column(Boolean, nullable=False, default=False)
    auth_provider = Column(String, nullable=False, default='email')
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Default shipping address fields (all optional)
    default_company = Column(String, nullable=True)
    default_country = Column(String, nullable=True)
    default_address_line1 = Column(String, nullable=True)
    default_address_line2 = Column(String, nullable=True)
    default_city = Column(String, nullable=True)
    default_state = Column(String, nullable=True)
    default_zip_code = Column(String, nullable=True)
    default_phone_number = Column(String, nullable=True)
    
    # --- Relationships ---
    # One-to-many relationship: A user can have many orders.
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    
    # One-to-one relationship: A user has one cart.
    cart = relationship("UserCart", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(email='{self.email}')>"