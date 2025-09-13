# /src/auth/ecommerce/order_service.py

import logging
from uuid import UUID
from sqlalchemy.orm import Session
from typing import List, Dict

from ..entities.user import User
from ..entities.order import Order, OrderItem, OrderStatus, PaymentStatus
from ..entities.user_cart import UserCart

logger = logging.getLogger(__name__)

def create_order_from_webhook(
    db: Session,
    user_id: str,
    payment_details: Dict,
    enriched_line_items: List[Dict]
) -> Order:
    """
    Creates and saves an Order and its OrderItems to the database.
    This function should be called within a single database transaction.
    
    Args:
        db (Session): The SQLAlchemy database session.
        user_id (str): The UUID of the user who made the purchase.
        payment_details (Dict): The Stripe checkout session object.
        enriched_line_items (List[Dict]): The list of purchased items, enriched with odoo_product_id.

    Returns:
        Order: The newly created SQLAlchemy Order object.
    """
    logger.info(f"Creating database order record for Stripe checkout ID: {payment_details['id']}")
    
    # 1. Create the main Order record
    new_order = Order(
        user_id=UUID(user_id),
        stripe_session_id=payment_details.get('id'),
        stripe_payment_intent_id=payment_details.get('payment_intent'),
        order_number=f"PO-{payment_details['id'][-12:].upper()}", # Create a human-readable order number
        status=OrderStatus.PROCESSING, # Payment is complete, so we are processing
        payment_status=PaymentStatus.PAID,
        total_amount=payment_details['amount_total'],
        shipping_address=payment_details.get('customer_details', {}), # Store customer details as JSON
        # You can add more fields here as needed
    )
    db.add(new_order)
    
    # 2. Create an OrderItem record for each item in the cart
    if not enriched_line_items:
        raise ValueError("Cannot create an order with no line items.")

    for item in enriched_line_items:
        new_order_item = OrderItem(
            order=new_order, # Associate this item with the new order
            product_id=str(item["odoo_product_id"]), # Odoo ID
            product_name=item['description'],
            quantity=item['quantity'],
            unit_price=item['price']['unit_amount'],
            total_price=item['amount_total']
        )
        db.add(new_order_item)
        
    logger.info(f"Successfully created order object for Stripe ID {new_order.stripe_session_id}")
    return new_order

def clear_user_cart(db: Session, user_id: str):
    """
    Clears a user's cart after a successful order.
    """
    logger.info(f"Attempting to clear cart for user_id: {user_id}")
    cart = db.query(UserCart).filter(UserCart.user_id == UUID(user_id)).first()
    
    if cart:
        cart.items = [] # Set items to an empty JSON array
        db.add(cart)
        logger.info(f"Cart for user_id: {user_id} has been cleared.")
    else:
        logger.warning(f"No cart found for user_id: {user_id} to clear.")