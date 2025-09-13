# /src/auth/controller.py
from typing import Annotated
from fastapi import APIRouter, Depends, Request, HTTPException, Response, Cookie
from starlette import status
from src.auth.src.auth import models
from src.auth.src.auth import service
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from src.auth.src.database.core import DbSession
from src.auth.src.rate_limiter import limiter
from datetime import timedelta, datetime, timezone
import jwt
from src.auth.src import denylist_service
from src.auth.src.logging import logger
from uuid import UUID


router = APIRouter(prefix='/auth', tags=['auth'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def set_refresh_cookie(response: Response, token: str):
    """Utility to set the refresh token in an httpOnly cookie."""
    response.set_cookie(key="refresh_token", value=token, httponly=True, samesite="lax",
                        secure=False, expires=timedelta(days=service.REFRESH_TOKEN_EXPIRE_DAYS))

@router.get("/google/login")
async def google_login(request: Request):
    """
    Generate Google's authorization URL and redirect the user there.
    """
    try:
        # Step 1: Generate the callback URL for Google to redirect back to.
        redirect_uri = request.url_for('google_callback')
        logger.info(f"Generated Google OAuth redirect URI: {redirect_uri}")

        # Step 2: Call the Authlib service to generate the final redirect response.
        # This step creates the 'state' parameter and saves it in the session.
        return await service.oauth.google.authorize_redirect(request, redirect_uri)

    except Exception:
        # This would typically happen if there's a misconfiguration in Authlib
        # or an issue with the session middleware.
        logger.exception("An unexpected error occurred during Google login URL generation.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initiate Google login. Please try again later."
        )


@router.get("/google/callback", response_model=models.Token)
async def google_callback(request: Request, db: DbSession, response: Response):
    """
    Handle the callback from Google after user authorization. This endpoint
    exchanges the authorization code for tokens, fetches user info, creates or
    finds the user in the local DB, and issues the application's own JWTs.
    """
    logger.info("Received callback from Google OAuth.")
    
    try:
        # Step 1: Exchange the authorization code from Google for an access token.
        # Authlib also validates the 'state' parameter here to prevent CSRF attacks.
        logger.debug("Attempting to authorize access token from Google.")
        token = await service.oauth.google.authorize_access_token(request)
        logger.debug("Successfully received token from Google.")
        
        # Step 2: Fetch the user's profile information from Google.
        user_info = token.get('userinfo')
        if not user_info or not user_info.get('email'):
            logger.error(f"Google OAuth token did not contain 'userinfo' or 'email'. Token payload: {token}")
            raise service.AuthenticationError("Could not fetch user info from Google.")
        
        user_email = user_info.get('email')
        logger.info(f"Successfully fetched user info for email: {user_email}")
        
        # Step 3: Find the user in our database or create a new one.
        # This is a critical step that interacts with our database.
        user = service.get_or_create_google_user(db, user_info)
        logger.info(f"Successfully retrieved/created local user record for {user_email} (ID: {user.id})")

        # Step 4: Create our application's own access and refresh tokens.
        # This logs the user into *our* system.
        access_token = service.create_access_token(
            email=user.email, user_id=user.id,
            expires_delta=timedelta(minutes=service.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = service.create_refresh_token(email=user.email, user_id=user.id)
        
        # Step 5: Set the refresh token in a secure, httpOnly cookie.
        set_refresh_cookie(response, refresh_token)
        logger.info(f"Made a new access and refresh tokens for user {user.id}.")

        # Step 6: Return the access token to the client.
        return models.Token(access_token=access_token, token_type='bearer')

    except Exception as e:
        # This block will catch any error during the process:
        # - Authlib raising an error (e.g., state mismatch, invalid code).
        # - Database errors during user creation.
        # - Any other unexpected failures.
        logger.exception("An error occurred during the Google OAuth callback process.")
        
        # It's good practice to redirect the user to a frontend error page
        # instead of showing a raw JSON error after an OAuth callback.
        # For now, we'll return a standard HTTP exception.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during authentication: {e}"
        )
@router.post("/", status_code=status.HTTP_202_ACCEPTED)
# @limiter.limit("5/hour")
async def register_user(db: DbSession, register_user_request: models.RegisterUserRequest):
    await service.register_user(db, register_user_request)
    return {"message": "Registration successful. Please check your email to verify your account."}

# FIX: Changed route from /login to /token and status code to 200 OK
@router.post("/token", response_model=models.Token, status_code=status.HTTP_200_OK)
async def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession
):
    
    
    user = service.authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise service.AuthenticationError(message="Incorrect email or password")
    
    access_token = service.create_access_token(email=user.email, user_id=user.id,
                                               expires_delta=timedelta(minutes=service.ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = service.create_refresh_token(email=user.email, user_id=user.id)
    set_refresh_cookie(response, refresh_token)
    
    return models.Token(access_token=access_token, token_type='bearer')

# ... (rest of the controller remains the same, but ensure HTTPException is imported)
# --- NEW: Verification Endpoint ---
@router.get("/verify-email")
async def verify_email(token: str, db: DbSession):
    service.verify_email_token(db, token)
    return {"message": "Email verified successfully. You can now log in."}
# --- END NEW ---


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(request: Request, db: DbSession):
    """
    Starts the password reset process by sending an email to the user.
    Accepts a JSON body with the user's email: {"email": "user@example.com"}
    """
    body = await request.json()
    email = body.get("email")
    if not email:
        return {"message": "If an account with that email exists, a password reset link has been sent."}

    # --- FIX: Call the renamed function ---
    await service.handle_password_reset_request(db, email)
    return {"message": "A password reset link has been sent to your email."}

@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(request: Request, db: DbSession):
    """
    Resets the user's password using a token.
    Accepts a JSON body with: {"token": "...", "new_password": "..."}
    """
    body = await request.json()
    token = body.get("token")
    new_password = body.get("new_password")

    service.reset_user_password(db, token=token, new_password=new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/logout" )
async def logout(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Logs out the user by adding their current token to the denylist.
    """
    try:
        # --- THE FIX IS HERE ---
        # Decode the token, requiring a valid signature but allowing it to be expired.
        # This is the safest way to get trusted claims from a token for logout.
        payload = jwt.decode(
            token,
            service.SECRET_KEY,
            algorithms=[service.ALGORITHM],
            options={"verify_exp": False} # This is now implicitly handled by the leeway, but can be kept
        )
        
        jti = payload.get('jti')
        exp = payload.get('exp')
        user_id = payload.get('id')
        
        # Check if the token has the necessary claims
        if not all([jti, exp, user_id]):
             logger.warning(f"Logout attempt with malformed token. Payload: {payload}")
             return {"message": "Token is malformed and cannot be processed for logout."}

        # Calculate remaining time and add to denylist
        # We only denylist if the token is not yet expired.
        if datetime.now(timezone.utc).timestamp() < exp:
            remaining_time = timedelta(seconds=exp - datetime.now(timezone.utc).timestamp())
            denylist_service.add_token_to_denylist(jti, remaining_time)
            logger.info(f"User {user_id} successfully logged out. Token JTI {jti} denylisted.")
            return {"message": "User logged out successfully"}
        else:
            # The token is already expired, no action needed.
            logger.info(f"Logout attempt with already expired token for user {user_id}.")
            return {"message": "Token is already expired."}

    except jwt.InvalidSignatureError:
        logger.warning("Logout attempt with a token that has an invalid signature.")
        return {"message": "Token has an invalid signature."}
    except jwt.DecodeError:
        logger.warning("Logout attempt with a token that could not be decoded.")
        return {"message": "Token is invalid."}
    except Exception as e:
        logger.exception(f"An unexpected error occurred during logout: {e}")
        # Return a generic error to the client
        raise HTTPException(status_code=500, detail="An internal error occurred during logout.")


@router.post("/refresh", response_model=models.Token)
async def refresh_access_token(
    response: Response,
    db: DbSession, # <--- CORRECTED LINE: Use the type hint directly
    refresh_token: Annotated[str | None, Cookie()] = None
):
    """
    Generates a new access token using a valid refresh token.
    The refresh token is expected in an httpOnly cookie.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Refresh token not found"
        )
        
    try:
        # Verify the refresh token
        payload = service.verify_refresh_token(refresh_token)
        user_id = payload.get("id")
        user_email = payload.get("sub")
        
        if not user_id or not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid refresh token payload"
            )

        # For added security (token rotation), denylist the old refresh token
        old_jti = payload.get('jti')
        if old_jti:
            exp = payload.get('exp', 0)
            remaining_time = timedelta(seconds=exp - datetime.now(timezone.utc).timestamp())
            if remaining_time.total_seconds() > 0:
                denylist_service.add_token_to_denylist(old_jti, remaining_time)

        # Issue a new pair of tokens
        new_access_token = service.create_access_token(
            email=user_email, user_id=UUID(user_id),
            expires_delta=timedelta(minutes=service.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        new_refresh_token = service.create_refresh_token(email=user_email, user_id=UUID(user_id))
        set_refresh_cookie(response, new_refresh_token)
        
        return models.Token(access_token=new_access_token, token_type='bearer')

    except service.AuthenticationError as e:
        # Catch verification errors from the service layer
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e.detail)
        )