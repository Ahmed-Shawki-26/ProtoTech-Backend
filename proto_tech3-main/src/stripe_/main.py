import os
import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from src.auth.logging import logger
# --- CORRECTED IMPORTS ---
# --- CORRECTED IMPORTS ---
# Use absolute paths from your single 'src' directory
from src.stripe_.schema.models import CheckoutRequest
from src.stripe_.services.stripe_sevrice import create_checkout_session, handle_webhook_event
from src.stripe_.services.email_service import send_email

# Import dependencies from the auth module using absolute paths
from src.auth.src.auth.service import CurrentUser
from src.auth.src.database.core import DbSession
from src.auth.src.users.service import get_user_by_id
# Load environment variables
env_path = ".env"
load_dotenv(dotenv_path=env_path)
os.makedirs("log/",exist_ok=True)

# Initialize FastAPI app
router = APIRouter()

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/checkout/")
async def checkout(
    data: CheckoutRequest,
    # --- THIS IS THE FIX ---
    # We remove the '= Depends()' part and let the Annotated type hint do the work.
    # Non-default parameters must come before default ones.
    db: DbSession,
    current_user_token: CurrentUser
):
    """
    Creates a Stripe checkout session for the authenticated user.
    """
    try:
        # Get the full user object from the database using the ID from the token
        user = get_user_by_id(db, current_user_token.get_uuid())
        
        # Pass the full user object and request data to the service
        url = await create_checkout_session(data, user)
        return {"url": url}
    except ValueError as e:
        # Catch validation errors from the service (e.g., product not found, insufficient stock)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook/")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handles incoming webhooks from Stripe."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        logger.warning("Invalid payload received in webhook")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid signature in webhook")
        raise HTTPException(status_code=401, detail="Invalid signature")

    logger.info(f"Webhook event received: {event['type']}")

    background_tasks.add_task(handle_webhook_event, event, send_email)

    return {"status": "ok"}