
# --- CORRECTED & UNIFIED IMPORTS ---
from src.stripe_.config.config import settings
from src.stripe_.schema.models import CheckoutRequest # This now implicitly imports CartItem
from src.auth.src.entities.user import User
from src.auth.src.ecommerce.service import get_product_by_id
from  src.auth.src.utils.update_inventory import adjust_inventory_after_purchase
from src.auth.logging import logger # Assuming a central logger
import stripe
import os
from typing import List, Dict, Any
from src.auth.src.database.core import SessionLocal
from src.auth.src.ecommerce.order_service import create_order_from_webhook, clear_user_cart

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



async def handle_webhook_event(event: Dict[str, Any], send_email_callback=None):
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