from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException
from . import models
from .models import User, ShippingAddressUpdate, ShippingAddressResponse
from ..auth.service import CurrentUser
from ..core.exceptions import (
    UserNotFoundError,
    InvalidPasswordError,
    PasswordMismatchError,
)
from ..utils.password_utils import verify_password, get_password_hash, is_password_strong
from ..core.infrastructure.logging import logger
from typing import Optional


class UserService:
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_default_shipping_address(db: Session, user_id: str) -> Optional[ShippingAddressResponse]:
        """Get user's default shipping address"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        return ShippingAddressResponse(
            company=user.default_company,
            country=user.default_country,
            address_line1=user.default_address_line1,
            address_line2=user.default_address_line2,
            city=user.default_city,
            state=user.default_state,
            zip_code=user.default_zip_code,
            phone_number=user.default_phone_number
        )
    
    @staticmethod
    def update_default_shipping_address(
        db: Session, 
        user_id: str, 
        shipping_data: ShippingAddressUpdate
    ) -> Optional[ShippingAddressResponse]:
        """Update user's default shipping address"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Update shipping address fields
        if shipping_data.company is not None:
            user.default_company = shipping_data.company
        if shipping_data.country is not None:
            user.default_country = shipping_data.country
        if shipping_data.address_line1 is not None:
            user.default_address_line1 = shipping_data.address_line1
        if shipping_data.address_line2 is not None:
            user.default_address_line2 = shipping_data.address_line2
        if shipping_data.city is not None:
            user.default_city = shipping_data.city
        if shipping_data.state is not None:
            user.default_state = shipping_data.state
        if shipping_data.zip_code is not None:
            user.default_zip_code = shipping_data.zip_code
        if shipping_data.phone_number is not None:
            user.default_phone_number = shipping_data.phone_number
        
        db.commit()
        db.refresh(user)
        
        return ShippingAddressResponse(
            company=user.default_company,
            country=user.default_country,
            address_line1=user.default_address_line1,
            address_line2=user.default_address_line2,
            city=user.default_city,
            state=user.default_state,
            zip_code=user.default_zip_code,
            phone_number=user.default_phone_number
        )


def get_user_by_id(db: Session, user_id: UUID) -> models.UserResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"User not found with ID: {user_id}")
        raise UserNotFoundError(user_id)
    logger.info(f"Successfully retrieved user with ID: {user_id}")
    return user


def change_password(
    db: Session, user_id: UUID, password_change: models.PasswordChange
) -> None:
    try:
        # In a real app, the service shouldn't call itself. Let's get the user directly.
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFoundError(user_id)

        # Verify current password
        if not user.password_hash or not verify_password(password_change.current_password, user.password_hash):
            logger.warning(f"Invalid current password provided for user ID: {user_id}")
            raise InvalidPasswordError()
        
        # Verify new passwords match
        if password_change.new_password != password_change.new_password_confirm:
            logger.warning(f"Password mismatch during change attempt for user ID: {user_id}")
            raise PasswordMismatchError()
        
        # --- NEW: Add password strength validation ---
        if not is_password_strong(password_change.new_password):
            raise HTTPException(
                status_code=400,
                detail="New password is not strong enough. It must be at least 8 characters long and include an uppercase letter, a lowercase letter, a number, and a special character."
            )
        # --- END NEW ---

        # Update password
        user.password_hash = get_password_hash(password_change.new_password)
        db.commit()
        logger.info(f"Successfully changed password for user ID: {user_id}")
    except Exception as e:
        logger.error(
            f"Error during password change for user ID: {user_id}. Error: {str(e)}"
        )
        raise
