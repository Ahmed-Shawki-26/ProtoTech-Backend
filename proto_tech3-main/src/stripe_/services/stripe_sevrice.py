
# --- CORRECTED & UNIFIED IMPORTS ---
from src.stripe_.config.config import settings
from src.stripe_.schema.models import CheckoutRequest # This now implicitly imports CartItem
from src.auth.src.entities.user import User
from src.auth.src.ecommerce.service import get_product_by_id
from  src.auth.src.utils.update_inventory import adjust_inventory_after_purchase
from src.auth.logging import logger # Assuming a central logger
import stripe
from uuid import UUID
import os
from typing import List, Dict, Any
from src.auth.src.database.core import SessionLocal
from src.auth.src.ecommerce.order_service import create_order_from_webhook, clear_user_cart
import json

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def create_checkout_session(data: CheckoutRequest, current_user: User) -> str:
    """
    Creates a Stripe Checkout session for a shopping cart of items after
    validating each one with Odoo.
    """
    try:
        line_items = []
        metadata = {
            "user_db_id": str(current_user.id),
            "customer_email": current_user.email,
        }
        
        for i, item in enumerate(data.cart_items):
            logger.info(f"Processing cart item {i+1}: Product ID {item.odoo_product_id}, Quantity: {item.quantity}")
            
            product_odoo = await get_product_by_id(item.odoo_product_id)
            if not product_odoo:
                raise ValueError(f"Product with Odoo ID {item.odoo_product_id} not found in cart.")

            price_from_odoo = product_odoo.get('list_price', 0.0)
            product_name = product_odoo.get('name', 'Unnamed Product')
            stock_available = product_odoo.get('qty_available', 0.0)

            if price_from_odoo <= 0:
                raise ValueError(f"Product '{product_name}' has an invalid price.")
            if stock_available < item.quantity:
                raise ValueError(f"Insufficient stock for '{product_name}'. Requested: {item.quantity}, Available: {stock_available}")

            line_items.append({
                "price_data": {
                    "currency": settings.CURRENCY,
                    "product_data": {"name": product_name},
                    # price for one unit of product 
                    "unit_amount": int(price_from_odoo * 100),
                },
                "quantity": item.quantity,
            })
            
            metadata[f"item_{i}_odoo_id"] = str(item.odoo_product_id)
            metadata[f"item_{i}_quantity"] = str(item.quantity)

        if not line_items:
            raise ValueError("Cannot create a checkout session for an empty cart.")
            
        logger.info(f"Creating Stripe session for user {current_user.email} with {len(line_items)} line item(s).")

        session = stripe.checkout.Session.create(
            line_items=line_items,
            mode="payment",
            success_url=settings.SUCCESS_URL,
            cancel_url=settings.CANCEL_URL,
            customer_email=current_user.email,
            metadata=metadata
        )
        return session.url

    except stripe.error.StripeError as e:
        logger.exception("Stripe error occurred.")
        raise
    except ValueError:
        raise
    except Exception:
        logger.exception("An unexpected error occurred in create_checkout_session.")
        raise



async def handle_odoo_order_webhook(event: Dict[str, Any], send_email_callback=None):
    """
    Handles 'checkout.session.completed' by:
    1. Creating an Order record in the local database.
    2. Clearing the user's cart.
    3. Updating inventory in Odoo for each item.
    4. Sending a confirmation email.
    This entire process is handled in a single database transaction.
    """
    if event["type"] != "checkout.session.completed":
        return

    payment = event["data"]["object"]
    metadata = payment.get("metadata", {})
    order_id = payment.get("id")
    
    # Get a new database session for this background task
    db = SessionLocal()
    try:
        # --- 1. Data Extraction and Validation ---
        user_db_id = metadata.get("user_db_id")
        if not user_db_id:
            logger.error(f"CRITICAL: Webhook for order {order_id} is missing 'user_db_id' in metadata. Cannot create order.")
            return

        # Fetch full line item details from Stripe
        session_with_line_items = stripe.checkout.Session.retrieve(order_id, expand=['line_items'])
        line_items = session_with_line_items.line_items
        if not line_items or not line_items.data:
            logger.error(f"CRITICAL: Could not retrieve line items for order {order_id}. Cannot process order.")
            return

        # Enrich line items with Odoo Product ID from metadata for easier processing
        enriched_line_items = []
        # loop on each orderd product in the whole order  
        for i, item in enumerate(line_items.data):
            odoo_id = metadata.get(f"item_{i}_odoo_id")
            if odoo_id:
                enriched_line_items.append({
                    "description": item.description,
                    "quantity": item.quantity,
                    "price": {"unit_amount": item.price.unit_amount},
                    "amount_total": item.amount_total,
                    "odoo_product_id": int(odoo_id)
                })

        # --- 2. Database Transaction ---
        logger.info(f"Starting database transaction for order {order_id}.")
        # Create the Order and OrderItems
        create_order_from_webhook(db, user_id=user_db_id, payment_details=payment, enriched_line_items=enriched_line_items)
        # Clear the user's cart
        clear_user_cart(db, user_id=user_db_id)
        
        db.commit()
        logger.info(f"Successfully committed database changes for order {order_id}.")
        
        # --- 3. External Service Calls (Post-Transaction) ---
        # These are called after our DB is safely committed. If these fail, we have a record
        # of the order and can retry or manually intervene.
        
        # Update Odoo Inventory
        for item in enriched_line_items:
            await adjust_inventory_after_purchase(
                product_id=item["odoo_product_id"],
                purchased_quantity=float(item["quantity"])
            )
        
        # Send Confirmation Email
        if send_email_callback:
            send_email_callback(payment_details=payment, line_items=line_items)

    except Exception:
        # If anything fails, roll back the entire transaction
        logger.exception(f"CRITICAL: Failed to process webhook for order {order_id}. Rolling back database changes.")
        db.rollback()
    finally:
        # Always close the session
        db.close()

from src.app.services.pcb_order_service import create_pcb_order
from src.app.schemas.pcb import ManufacturingParameters, BoardDimensions, PriceQuote

# ... (existing create_checkout_session and handle_webhook_event for e-commerce) ...


# --- NEW: Function for PCB Checkout ---
async def create_pcb_checkout_session(
    params: ManufacturingParameters,
    dimensions: BoardDimensions,
    quote: PriceQuote,
    current_user: User
) -> str:
    """
    Creates a Stripe Checkout session specifically for a PCB order.
    """
    try:
        logger.info(f"Creating PCB checkout session for user {current_user.email}")

        # The price is already calculated, so we use it directly.
        price_in_cents = int(quote.final_price_egp * 100)
        
        # We need to serialize the Pydantic models to a JSON string for Stripe metadata
        params_json_str = params.model_dump_json()
        dimensions_json_str = dimensions.model_dump_json()
        logger.info(f"here are dim: {dimensions_json_str}")
        session = stripe.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": settings.CURRENCY,
                    "product_data": {"name": f"Custom PCB Order ({dimensions.width_mm}x{dimensions.height_mm}mm)"},
                    "unit_amount": price_in_cents,
                },
                "quantity": 1, # A PCB quote is for a single "job"
            }],
            mode="payment",
            success_url=settings.SUCCESS_URL,
            cancel_url=settings.CANCEL_URL,
            customer_email=current_user.email,
            metadata={
                "order_type": "pcb", # CRITICAL: To distinguish from e-commerce orders
                "user_db_id": str(current_user.id),
                "manufacturing_params": params_json_str,
                "dimensions": dimensions_json_str,
            }
        )
        return session.url
    except Exception:
        logger.exception("An unexpected error occurred in create_pcb_checkout_session.")
        raise


# --- REVISED: Webhook handler to route to the correct service ---
async def handle_webhook_event(event: Dict[str, Any], send_email_callback=None):
    if event["type"] != "checkout.session.completed":
        return

    payment = event["data"]["object"]
    metadata = payment.get("metadata", {})
    order_id = payment.get("id")
    
    # --- NEW: Routing logic based on metadata ---
    order_type = metadata.get("order_type")
    
    if order_type == "pcb":
        await handle_pcb_order_webhook(payment)
    else:
        # Default to the existing e-commerce/Odoo flow
        await handle_odoo_order_webhook(payment, send_email_callback)

# --- NEW: Specific handler for PCB order webhooks ---
async def handle_pcb_order_webhook(payment: Dict[str, Any]):
    metadata = payment.get("metadata", {})
    order_id = payment.get("id")
    user_db_id = metadata.get("user_db_id")
    dimensions = json.loads(metadata.get("dimensions",{}))
    width=dimensions.get("width_mm")
    height=dimensions.get("height_mm")
    if not user_db_id:
        logger.error(f"CRITICAL: PCB webhook for order {order_id} is missing 'user_db_id'.")
        return

    db = SessionLocal()
    try:
        from src.auth.src.users.service import get_user_by_id
        
        user = get_user_by_id(db, UUID(user_db_id))
        if not user:
            raise ValueError(f"User with ID {user_db_id} not found.")

        # De-serialize the JSON strings from metadata
        manufacturing_params = json.loads(metadata.get("manufacturing_params", "{}"))
        
        # Create the order record in our database
        create_pcb_order(
            db=db,
            user=user,
            payment_details=payment,
            manufacturing_params=manufacturing_params,
            width_mm=width,
            height_mm=height
        )
        db.commit()
        logger.info(f"Successfully created PCB Order record for Stripe ID {order_id}")
        
        # Here you could add another email notification for PCB orders
        
    except Exception:
        db.rollback()
        logger.exception(f"CRITICAL: Failed to process PCB webhook for order {order_id}. DB rolled back.")
    finally:
        db.close()