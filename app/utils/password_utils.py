# /src/auth/password_utils.py

import re
from passlib.context import CryptContext
import logging

logger = logging.getLogger(__name__)

# Create the context once and reuse it
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def is_password_strong(password: str) -> bool:
    """
    Checks if a password meets the strength requirements.
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a hashed password.
    """
    return bcrypt_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password.
    """
    try:
        return bcrypt_context.hash(password)
    except Exception:
        logger.exception("Error occurred while hashing password.")
        raise