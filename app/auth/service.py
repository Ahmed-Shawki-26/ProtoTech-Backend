# /src/auth/service.py

from datetime import timedelta, datetime, timezone
from typing import Annotated, Optional
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
import jwt
from jwt import PyJWTError
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import os
import logging

# Import from correct paths - import User directly to avoid circular imports
from ..schemas.user import User
from . import models
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from ..exceptions import AuthenticationError, UserNotFoundError
from ..logging import logger
from ..email_service import send_verification_email, send_password_reset_email
from .. import denylist_service
from ..utils.password_utils import is_password_strong, verify_password, get_password_hash

load_dotenv()

# --- Configuration ---
SECRET_KEY = os.getenv("ENCODING_SECRET_KEY") or "dev-secret-change-me"
ALGORITHM = os.getenv("ENCODING_ALGORITHM", "HS256")
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS", "24"))
# Respect environment overrides for token lifetimes (fallback to sensible defaults)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_HOURS", "1"))

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/token')

# --- OAuth Configuration ---
def get_google_oauth():
    """Get configured Google OAuth client."""
    try:
        # Create a new OAuth instance for each request
        from authlib.integrations.starlette_client import OAuth
        oauth_instance = OAuth()
        
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        if not client_id or not client_secret:
            logger.error("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in environment")
            raise HTTPException(status_code=500, detail="Google OAuth is not configured properly (missing client id/secret)")

        oauth_instance.register(
            name='google',
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        
        return oauth_instance.google
    except Exception as e:
        logger.error(f"Error configuring Google OAuth: {repr(e)}")
        raise HTTPException(status_code=500, detail="Google OAuth configuration failed")

def get_or_create_google_user(db: Session, user_info: dict) -> User:
    """Get existing user or create new one from Google OAuth."""
    try:
        user = db.query(User).filter(User.email == user_info['email']).first()
        if user:
            if user.auth_provider != 'google':
                logger.warning(f"User with email {user.email} tried to log in with Google, but has an existing '{user.auth_provider}' account.")
            return user
        else:
            new_user = User(
                id=uuid4(), 
                email=user_info['email'], 
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''), 
                password_hash=None, 
                is_verified=True,
                auth_provider='google'
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            logger.info(f"Created new user via Google login: {new_user.email}")
            return new_user
    except Exception as e:
        logger.error(f"Error in get_or_create_google_user: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create Google user")

def authenticate_user(email: str, password: str, db: Session) -> Optional[User]:
    """Authenticates a user with email and password."""
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not user.password_hash:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
            
        if not user.is_verified:
            logger.warning(f"Login attempt from unverified user: {email}")
            raise AuthenticationError(message="Please verify your email address before logging in.")
            
        return user
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Error in authenticate_user: {e}")
        return None

def create_access_token(email: str, user_id: UUID, expires_delta: timedelta) -> str:
    """Creates a new JWT access token with a unique ID (jti)."""
    try:
        expire = datetime.now(timezone.utc) + expires_delta
        jti = str(uuid4())
        encode = {
            'sub': email, 
            'id': str(user_id), 
            'exp': expire, 
            'scope': 'access_token', 
            'jti': jti,
            'type': 'access'
        }
        return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Error creating access token: {e}")
        raise HTTPException(status_code=500, detail="Failed to create access token")

def create_refresh_token(email: str, user_id: UUID) -> str:
    """Creates a new, long-lived JWT refresh token."""
    try:
        expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        jti = str(uuid4())
        encode = {
            'sub': email, 
            'id': str(user_id), 
            'exp': expires, 
            'scope': 'refresh_token', 
            'jti': jti,
            'type': 'refresh'
        }
        return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Error creating refresh token: {e}")
        raise HTTPException(status_code=500, detail="Failed to create refresh token")

def verify_token(token: str) -> models.TokenData:
    """Decodes and verifies an access token, and checks if it's denylisted."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check token scope
        if payload.get('scope') != 'access_token':
            raise AuthenticationError(message="Invalid token scope")
            
        # Check JTI
        jti = payload.get('jti')
        if not jti:
            raise AuthenticationError(message="Token is missing JTI.")
            
        # Check if token is denylisted
        if denylist_service.is_token_denylisted(jti):
            raise AuthenticationError(message="Token has been revoked.")
            
        # Check user ID
        user_id = payload.get('id')
        if not user_id:
            raise AuthenticationError(message="User ID not found in token.")
            
        return models.TokenData(user_id=user_id)
        
    except PyJWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise AuthenticationError(message="Invalid token")
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in verify_token: {e}")
        raise AuthenticationError(message="Token verification failed")

def verify_refresh_token(token: str) -> models.TokenData:
    """Decodes and verifies a refresh token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check token scope
        if payload.get('scope') != 'refresh_token':
            raise AuthenticationError(message="Invalid refresh token scope")
            
        # Check JTI
        jti = payload.get('jti')
        if not jti:
            raise AuthenticationError(message="Refresh token is missing JTI.")
            
        # Check if token is denylisted
        if denylist_service.is_token_denylisted(jti):
            raise AuthenticationError(message="Refresh token has been revoked.")
            
        # Check user ID
        user_id = payload.get('id')
        if not user_id:
            raise AuthenticationError(message="User ID not found in refresh token.")
            
        return models.TokenData(user_id=user_id)
        
    except PyJWTError as e:
        logger.warning(f"JWT decode error for refresh token: {e}")
        raise AuthenticationError(message="Invalid refresh token")
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in verify_refresh_token: {e}")
        raise AuthenticationError(message="Refresh token verification failed")

def get_refresh_token_payload(token: str) -> dict:
    """Decode refresh token and return its payload (with basic validation)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('scope') != 'refresh_token':
            raise AuthenticationError(message="Invalid refresh token scope")
        return payload
    except PyJWTError as e:
        logger.warning(f"JWT decode error for refresh token payload: {e}")
        raise AuthenticationError(message="Invalid refresh token")

def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]) -> models.TokenData:
    """FastAPI dependency to get the current user from a token."""
    return verify_token(token)

CurrentUser = Annotated[models.TokenData, Depends(get_current_user)]

def create_email_verification_token(email: str) -> str:
    """Creates a token for email verification."""
    try:
        expire = datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
        encode = {
            'sub': email,
            'exp': expire,
            'scope': 'email_verification',
            'jti': str(uuid4())
        }
        return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Error creating email verification token: {e}")
        raise HTTPException(status_code=500, detail="Failed to create verification token")

def create_password_reset_token(email: str) -> str:
    """Creates a token for password reset."""
    try:
        expire = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
        encode = {
            'sub': email,
            'exp': expire,
            'scope': 'password_reset',
            'jti': str(uuid4())
        }
        return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    except Exception as e:
        logger.error(f"Error creating password reset token: {e}")
        raise HTTPException(status_code=500, detail="Failed to create reset token")

def verify_email_token(db: Session, token: str) -> User:
    """Verifies an email verification token and marks user as verified."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get('scope') != 'email_verification':
            raise AuthenticationError("Invalid token scope for email verification")
            
        email = payload.get('sub')
        if not email:
            raise AuthenticationError("Email not found in token")
            
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise AuthenticationError("User not found")
            
        if user.is_verified:
            raise AuthenticationError("Email already verified")
            
        user.is_verified = True
        db.commit()
        db.refresh(user)
        
        logger.info(f"Email verified for user: {email}")
        return user
        
    except PyJWTError:
        raise AuthenticationError("Invalid or expired verification token")
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Error in verify_email_token: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Email verification failed")

async def register_user(db: Session, register_user_request: models.RegisterUserRequest) -> None:
    """Registers a new user, validating password strength, and sends a verification email."""
    try:
        # Validate password strength
        if not is_password_strong(register_user_request.password):
            raise HTTPException(
                status_code=400, 
                detail="Password is not strong enough. It must be at least 8 characters long and include an uppercase letter, a lowercase letter, a number, and a special character."
            )
            
        # Check for existing user
        existing_user = db.query(User).filter(User.email == register_user_request.email).first()
        if existing_user:
            raise AuthenticationError(message="Email already registered.")
        
        # Create user
        create_user_model = User(
            id=uuid4(), 
            email=register_user_request.email, 
            first_name=register_user_request.first_name,
            last_name=register_user_request.last_name, 
            password_hash=get_password_hash(register_user_request.password)
        )
        db.add(create_user_model)
        db.commit()
        db.refresh(create_user_model)
        
        # Send verification email
        logger.info(f"Successfully registered user: {register_user_request.email}. Sending verification email.")
        verification_token = create_email_verification_token(email=create_user_model.email)
        frontend_url = os.getenv("FRONTEND_BASE_URL", "https://proto-tech-frontend.vercel.app")
        verification_link = f"{frontend_url}/verify-email?token={verification_token}"
        
        await send_verification_email(
            recipient_email=create_user_model.email, 
            verification_link=verification_link,
            first_name=create_user_model.first_name
        )
        
    except (AuthenticationError, HTTPException):
        raise
    except Exception as e:
        logger.exception(f"Registration failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")

async def handle_password_reset_request(db: Session, email: str) -> None:
    """Handles password reset request by sending reset email."""
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            # Don't reveal if user exists or not
            logger.info(f"Password reset requested for non-existent email: {email}")
            return
            
        if not user.is_verified:
            logger.warning(f"Password reset requested for unverified user: {email}")
            return
            
        # Create reset token
        reset_token = create_password_reset_token(email)
        frontend_url = os.getenv("FRONTEND_BASE_URL", "https://proto-tech-frontend.vercel.app")
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"
        
        # Send reset email
        await send_password_reset_email(
            recipient_email=user.email,
            reset_link=reset_link,
            first_name=user.first_name
        )
        
        logger.info(f"Password reset email sent to: {email}")
        
    except Exception as e:
        logger.error(f"Error in handle_password_reset_request: {e}")
        # Don't expose internal errors to user

async def reset_password(db: Session, token: str, new_password: str) -> None:
    """Resets user password using reset token."""
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        if payload.get('scope') != 'password_reset':
            raise AuthenticationError("Invalid token scope for password reset")
            
        email = payload.get('sub')
        if not email:
            raise AuthenticationError("Email not found in token")
            
        # Find user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise AuthenticationError("User not found")
            
        # Validate new password
        if not is_password_strong(new_password):
            raise HTTPException(
                status_code=400, 
                detail="Password is not strong enough"
            )
            
        # Update password
        user.password_hash = get_password_hash(new_password)
        db.commit()
        
        # Blacklist all user tokens (force re-login)
        # Note: This would require implementing a method to get all user tokens
        logger.info(f"Password reset successful for user: {email}")
        
    except PyJWTError:
        raise AuthenticationError("Invalid or expired reset token")
    except (AuthenticationError, HTTPException):
        raise
    except Exception as e:
        logger.error(f"Error in reset_password: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Password reset failed")