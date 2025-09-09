from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.auth.src.users import models
from src.auth.src.entities.user import User
from src.auth.src.exceptions import (
    UserNotFoundError,
    InvalidPasswordError,
    PasswordMismatchError,
)
from src.auth.src.utils.password_utils import verify_password, get_password_hash, is_password_strong
from src.auth.src.logging import logger


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
