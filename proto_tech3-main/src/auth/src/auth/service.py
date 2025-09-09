# /src/auth/service.py

from datetime import timedelta, datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
import jwt
from jwt import PyJWTError
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import os

from src.auth.src.entities.user import User
from src.auth.src.auth import models
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from src.auth.src.exceptions import AuthenticationError, UserNotFoundError
from src.auth.src.logging import logger
from src.auth.src.email_service import send_verification_email, send_password_reset_email
from src.auth.src import denylist_service
# FIX: This is now the single source of truth for all password-related functions
from src.auth.src.utils.password_utils import is_password_strong, verify_password, get_password_hash

load_dotenv()

# --- Configuration ---
SECRET_KEY = os.getenv("ENCODING_SECRET_KEY")
ALGORITHM = os.getenv("ENCODING_ALGORITHM", "HS256")
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS", "24"))
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # More secure, shorter life
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Long-lived refresh token
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token') # Correctly points to /token

# --- OAuth Configuration ---
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

def get_or_create_google_user(db: Session, user_info: dict) -> User:
    user = db.query(User).filter(User.email == user_info['email']).first()
    if user:
        if user.auth_provider != 'google':
            logger.warning(f"User with email {user.email} tried to log in with Google, but has an existing '{user.auth_provider}' account.")
        return user
    else:
        new_user = User(id=uuid4(), email=user_info['email'], first_name=user_info.get('given_name', ''),
                        last_name=user_info.get('family_name', ''), password_hash=None, is_verified=True,
                        auth_provider='google')
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"Created new user via Google login: {new_user.email}")
        return new_user

def authenticate_user(email: str, password: str, db: Session) -> User | None:
    """Authenticates a user with email and password."""
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return None
    if not user.is_verified:
        logger.warning(f"Login attempt from unverified user: {email}")
        raise AuthenticationError(message="Please verify your email address before logging in.")
    return user

def create_access_token(email: str, user_id: UUID, expires_delta: timedelta) -> str:
    """Creates a new JWT access token with a unique ID (jti)."""
    expire = datetime.now(timezone.utc) + expires_delta
    encode = {'sub': email, 'id': str(user_id), 'exp': expire, 'scope': 'access_token', 'jti': str(uuid4())}
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(email: str, user_id: UUID) -> str:
    """Creates a new, long-lived JWT refresh token."""
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    encode = {'sub': email, 'id': str(user_id), 'exp': expires, 'scope': 'refresh_token', 'jti': str(uuid4())}
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> models.TokenData:
    """Decodes and verifies an access token, and checks if it's denylisted."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('scope') != 'access_token':
            raise AuthenticationError(message="Invalid token scope")
        jti = payload.get('jti')
        if not jti:
            raise AuthenticationError(message="Token is missing JTI.")
        if denylist_service.is_token_denylisted(jti):
            raise AuthenticationError(message="Token has been revoked.")
        user_id = payload.get('id')
        if not user_id:
            raise AuthenticationError(message="User ID not found in token.")
        return models.TokenData(user_id=user_id)
    except PyJWTError as e:
        logger.warning(f"Token verification failed: {str(e)}")
        raise AuthenticationError("Could not validate credentials")

def verify_refresh_token(token: str) -> dict:
    """Decodes and verifies a refresh token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('scope') != 'refresh_token':
            raise AuthenticationError(message="Invalid token scope for refresh")
        jti = payload.get('jti')
        if not jti:
            raise AuthenticationError(message="Refresh token is missing JTI.")
        if denylist_service.is_token_denylisted(jti):
            raise AuthenticationError(message="Refresh token has been revoked.")
        return payload
    except PyJWTError as e:
        logger.warning(f"Refresh token verification failed: {str(e)}")
        raise AuthenticationError("Could not validate refresh token")

def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]) -> models.TokenData:
    """FastAPI dependency to get the current user from a token."""
    return verify_token(token)

CurrentUser = Annotated[models.TokenData, Depends(get_current_user)]

def create_email_verification_token(email: str) -> str:
    """Creates a new JWT for email verification."""
    expires = datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    encode = {'sub': email, 'exp': expires, 'scope': 'email_verification'}
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_email_token(db: Session, token: str) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('scope') != 'email_verification':
            raise AuthenticationError(message="Invalid token scope")
        email = payload.get('sub')
        if not email:
            raise AuthenticationError("Invalid token: email missing")
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise UserNotFoundError()
        if user.is_verified:
            logger.info(f"User {email} is already verified.")
            return user
        user.is_verified = True
        db.commit()
        db.refresh(user)
        logger.info(f"Successfully verified email for user: {email}")
        return user
    except PyJWTError as e:
        logger.error(f"Email verification token failed: {str(e)}")
        raise AuthenticationError("Invalid or expired verification token")

async def register_user(db: Session, register_user_request: models.RegisterUserRequest) -> None:
    """
    Registers a new user, validating password strength, creating the DB record,
    and sending a verification email in a single transaction.
    """
    email = register_user_request.email
    logger.info(f"Registration process started for email: {email}")

    # --- 1. Password Strength Validation ---
    if not is_password_strong(register_user_request.password):
        logger.warning(f"Registration failed for {email}: Weak password provided.")
        raise HTTPException(
            status_code=400,
            detail="Password is not strong enough. It must be at least 8 characters long and include an uppercase letter, a lowercase letter, a number, and a special character."
        )
    logger.debug(f"Password for {email} meets strength requirements.")

    # --- 2. Database and Email Operations ---
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            logger.warning(f"Registration failed for {email}: Email already registered.")
            raise AuthenticationError(message="Email already registered.")
        
        logger.debug(f"Email {email} is available. Creating new user object.")
        
        # Create the new user object
        create_user_model = User(
            id=uuid4(),
            email=email,
            first_name=register_user_request.first_name,
            last_name=register_user_request.last_name,
            password_hash=get_password_hash(register_user_request.password)
        )
        
        logger.debug(f"Adding user {email} to the database session.")
        db.add(create_user_model)
        db.commit()
        db.refresh(create_user_model)
        logger.info(f"Successfully committed user {email} to the database (ID: {create_user_model.id}).")

        # --- 3. Email Sending ---
        logger.debug(f"Preparing to send verification email to {email}.")
        verification_token = create_email_verification_token(email=create_user_model.email)
        base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
        verification_link = f"{base_url}/auth/verify-email?token={verification_token}"
        
        await send_verification_email(
            recipient_email=create_user_model.email,
            verification_link=verification_link,
            first_name=create_user_model.first_name
        )
        logger.info(f"Verification email successfully sent to {email}.")

    except AuthenticationError:
        # Re-raise the specific "Email already registered" error to return a 401
        raise

    except Exception as e:
        # --- CRITICAL: Error Handling & Rollback ---
        logger.exception(f"An unexpected error occurred during the registration process for {email}. Rolling back database changes.")
        
        # If an error occurs (e.g., email server is down), we must roll back
        # the user creation to prevent a user from existing in the DB without
        # ever receiving a verification email.
        db.rollback()
        
        # Re-raise as a generic 500 error to the client
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later."
        )
# This function is now removed, as its logic is inside the controller's login endpoint.
# The controller should be responsible for orchestrating the creation of both tokens.

def create_password_reset_token(email: str) -> str:
    """Creates a new, short-lived JWT for password reset."""
    expires = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    encode = {'sub': email, 'exp': expires, 'scope': 'password_reset'}
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

async def handle_password_reset_request(db: Session, email: str):
    user = db.query(User).filter(User.email == email).first()
    if user and user.auth_provider == 'email':
        password_reset_token = create_password_reset_token(email=user.email)
        base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
        reset_link = f"{base_url}/reset-password-page?token={password_reset_token}" 
        await send_password_reset_email(recipient_email=user.email, reset_link=reset_link, first_name=user.first_name)
    else:
        logger.info(f"Password reset requested for non-existent or social account: {email}")

def reset_user_password(db: Session, token: str, new_password: str) -> None:
    """Verifies a password reset token and updates the user's password."""
    if not new_password:
        raise HTTPException(status_code=400, detail="Password cannot be empty.")
    if not is_password_strong(new_password):
        raise HTTPException(status_code=400, detail="New password is not strong enough.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get('scope') != 'password_reset':
            raise AuthenticationError(message="Invalid token scope")
        email = payload.get('sub')
        if not email:
            raise AuthenticationError("Invalid token: email missing")
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise UserNotFoundError()
        user.password_hash = get_password_hash(new_password)
        db.commit()
        logger.info(f"Successfully reset password for user: {email}")
    except PyJWTError as e:
        logger.error(f"Password reset token failed: {str(e)}")
        raise AuthenticationError("Invalid or expired password reset token")