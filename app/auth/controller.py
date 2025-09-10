# /src/auth/controller.py
from typing import Annotated
from fastapi import APIRouter, Depends, Request, HTTPException, Response, Cookie
from starlette import status
from . import models
from . import service
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from ..database.core import DbSession
from ..rate_limiter import limiter
from datetime import timedelta, datetime, timezone
import jwt
from .. import denylist_service
from ..logging import logger
from uuid import UUID, uuid4
import os
from urllib.parse import quote

router = APIRouter(prefix='/auth', tags=['auth'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def set_refresh_cookie(response: Response, token: str):
    """Utility to set the refresh token in an httpOnly cookie."""
    response.set_cookie(
        key="refresh_token", 
        value=token, 
        httponly=True, 
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
        max_age=service.REFRESH_TOKEN_EXPIRE_DAYS * 86400  # Convert days to seconds
    )

def clear_refresh_cookie(response: Response):
    """Utility to clear the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )

@router.get("/google/login")
async def google_login(request: Request):
    """Generate Google's authorization URL and redirect the user there."""
    try:
        logger.info("Google OAuth login initiated")
        # Allow explicit override to avoid redirect_uri_mismatch
        configured_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        redirect_uri = configured_redirect_uri or request.url_for('google_callback')
        # Normalize to /api/v1/auth/* to match mounted router path
        if redirect_uri.startswith("http://localhost:8000/auth/"):
            redirect_uri = redirect_uri.replace("/auth/", "/api/v1/auth/")
        elif redirect_uri.startswith("http://127.0.0.1:8000/auth/"):
            redirect_uri = redirect_uri.replace("/auth/", "/api/v1/auth/")
        logger.info(f"Redirect URI: {redirect_uri} (override={'set' if configured_redirect_uri else 'auto'})")
        if not configured_redirect_uri:
            logger.warning("GOOGLE_REDIRECT_URI not set; using auto-generated URL. Ensure this exact URL is authorized in Google Console.")
        client_id_present = bool(os.getenv('GOOGLE_CLIENT_ID'))
        client_secret_present = bool(os.getenv('GOOGLE_CLIENT_SECRET'))
        if not (client_id_present and client_secret_present):
            logger.error("Missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET; aborting login")
            raise HTTPException(status_code=500, detail="Google OAuth is not configured properly")
        
        google_oauth = service.get_google_oauth()
        logger.info("Google OAuth client obtained successfully")
        
        # Capture optional next redirect target and store in session for callback
        next_target = request.query_params.get("next")
        if next_target:
            # Store in session so callback can read it later
            request.session['post_auth_next'] = next_target

        # Explicitly set a state and touch the session so cookie is written
        state_value = uuid4().hex
        request.session['oauth_csrf_pre'] = state_value
        
        # Force top-level redirect and pass state explicitly
        return await google_oauth.authorize_redirect(
            request,
            redirect_uri,
            prompt='consent',
            state=state_value
        )
    except Exception as e:
        logger.error(f"Google OAuth login error: {repr(e)}")
        # Send a concise but helpful error back to client
        raise HTTPException(status_code=500, detail=f"Google OAuth login failed: {getattr(e, 'detail', str(e))}")

@router.get("/google/callback", response_model=models.Token)
async def google_callback(request: Request, db: DbSession, response: Response):
    """Handle the callback from Google after user authorization."""
    try:
        google_oauth = service.get_google_oauth()
        token = await google_oauth.authorize_access_token(request)
        user_info = token.get('userinfo')
        if not user_info:
            # Fallback: explicitly call the userinfo endpoint
            try:
                resp = await google_oauth.get('userinfo', token=token)
                user_info = resp.json()
            except Exception as inner_e:
                logger.error(f"Failed to fetch userinfo from Google: {inner_e}")
                user_info = None
        if not user_info or not user_info.get('email'):
            raise HTTPException(status_code=400, detail="Could not fetch user info from Google.")
        
        user = service.get_or_create_google_user(db, user_info)
        access_token = service.create_access_token(
            email=user.email, 
            user_id=user.id,
            expires_delta=timedelta(minutes=service.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = service.create_refresh_token(email=user.email, user_id=user.id)
        set_refresh_cookie(response, refresh_token)
        
        # Redirect to frontend with access token
        frontend_url = os.getenv("FRONTEND_BASE_URL", "https://proto-tech-frontend.vercel.app")
        # Use next from session if available
        next_target = request.session.pop('post_auth_next', None)
        redirect_url = f"{frontend_url}/oauth-callback?token={access_token}&type=google"
        if next_target:
            redirect_url += f"&next={quote(str(next_target))}"
        
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=redirect_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth callback error: {repr(e)}")
        # Surface the reason during development to diagnose issues like state mismatch
        raise HTTPException(status_code=500, detail=f"Google authentication failed: {str(e)}")

@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/hour")  # Increased rate limit for development
async def register_user(
    request: Request,
    db: DbSession, 
    register_user_request: models.RegisterUserRequest
):
    """Register a new user account."""
    try:
        await service.register_user(db, register_user_request)
        return {
            "message": "Registration successful. Please check your email to verify your account.",
            "email": register_user_request.email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/token", response_model=models.Token, status_code=status.HTTP_200_OK)
@limiter.limit("50/hour")  # Increased rate limit for development
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession
):
    """Login user and return access token with refresh token in cookie."""
    try:
        user = service.authenticate_user(form_data.username, form_data.password, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Update last login
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        
        # Create tokens
        access_token = service.create_access_token(
            email=user.email, 
            user_id=user.id,
            expires_delta=timedelta(minutes=service.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = service.create_refresh_token(email=user.email, user_id=user.id)
        set_refresh_cookie(response, refresh_token)
        
        return models.Token(access_token=access_token, token_type='bearer')
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email_endpoint(
    verification: models.EmailVerification,
    db: DbSession
):
    """Verify user email using verification token."""
    try:
        service.verify_email_token(db, verification.token)
        return {"message": "Email verified successfully. You can now log in."}
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(status_code=400, detail="Email verification failed")

@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/day")  # Rate limit password reset requests
async def request_password_reset(
    request: Request,
    reset_request: models.PasswordResetRequest,
    db: DbSession
):
    """Request password reset via email."""
    try:
        await service.handle_password_reset_request(db, reset_request.email)
        return {
            "message": "If an account with that email exists, a password reset link has been sent."
        }
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        # Always return success to prevent email enumeration
        return {
            "message": "If an account with that email exists, a password reset link has been sent."
        }

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password_endpoint(
    reset_data: models.PasswordReset,
    db: DbSession
):
    """Reset password using reset token."""
    try:
        await service.reset_password(db, reset_data.token, reset_data.new_password)
        return {"message": "Password reset successful. You can now login with your new password."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(status_code=400, detail="Password reset failed")

@router.post("/refresh", response_model=models.Token)
async def refresh_access_token(
    request: Request,
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie()] = None
):
    """Generate new access token using refresh token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Refresh token not found"
        )
        
    try:
        # Verify the refresh token
        token_data = service.verify_refresh_token(refresh_token)
        user_id = token_data.get_uuid()
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid refresh token"
            )

        # Get user to get email
        user = db.query(service.User).filter(service.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Denylist the old refresh token (rotation)
        payload = service.get_refresh_token_payload(refresh_token)
        old_jti = payload.get('jti')
        exp = payload.get('exp')
        if old_jti and exp and datetime.now(timezone.utc).timestamp() < exp:
            remaining_time = timedelta(seconds=exp - datetime.now(timezone.utc).timestamp())
            denylist_service.add_token_to_denylist(old_jti, remaining_time)

        # Issue new tokens
        new_access_token = service.create_access_token(
            email=user.email, 
            user_id=user.id,
            expires_delta=timedelta(minutes=service.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        new_refresh_token = service.create_refresh_token(email=user.email, user_id=user.id)
        set_refresh_cookie(response, new_refresh_token)
        
        return models.Token(access_token=new_access_token, token_type='bearer')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token refresh failed")

@router.post("/logout", response_model=models.LogoutResponse)
async def logout_endpoint(
    request: Request,
    response: Response,
    token: Annotated[str, Depends(oauth2_scheme)]
):
    """Logout user and blacklist current token."""
    try:
        # Decode token to get JTI
        payload = jwt.decode(
            token,
            service.SECRET_KEY,
            algorithms=[service.ALGORITHM],
            options={"verify_exp": False}
        )
        
        jti = payload.get('jti')
        exp = payload.get('exp')
        user_id = payload.get('id')
        
        if not all([jti, exp, user_id]):
            logger.warning(f"Logout attempt with malformed token")
            return {"message": "Token is malformed and cannot be processed for logout."}

        # Add to denylist if not expired
        if datetime.now(timezone.utc).timestamp() < exp:
            remaining_time = timedelta(seconds=exp - datetime.now(timezone.utc).timestamp())
            denylist_service.add_token_to_denylist(jti, remaining_time)
            logger.info(f"User {user_id} successfully logged out. Token JTI {jti} denylisted.")
        else:
            logger.info(f"Logout attempt with already expired token for user {user_id}.")
        
        # Clear refresh cookie
        clear_refresh_cookie(response)
        
        return {"message": "User logged out successfully"}

    except jwt.InvalidSignatureError:
        logger.warning("Logout attempt with invalid token signature")
        return {"message": "Token has an invalid signature."}
    except jwt.DecodeError:
        logger.warning("Logout attempt with undecodable token")
        return {"message": "Token is invalid."}
    except Exception as e:
        logger.exception(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred during logout.")

@router.get("/me", response_model=models.UserResponse)
async def get_current_user_info(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession
):
    """Get current user information."""
    try:
        token_data = service.verify_token(token)
        user_id = token_data.get_uuid()
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(service.User).filter(service.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return models.UserResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user information")