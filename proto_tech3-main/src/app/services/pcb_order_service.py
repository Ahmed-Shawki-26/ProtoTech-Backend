# /src/pcb_quote/services/pcb_order_service.py

import logging
from uuid import UUID
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.auth.src.entities.pcb_order import PcbOrder, OrderStatus
from src.auth.src.entities.user import User

logger = logging.getLogger(__name__)

def create_pcb_order(
    db: Session,
    user: User,
    width_mm : float , 
    height_mm : float , 
    payment_details: Dict[str, Any],
    manufacturing_params: Dict[str, Any]
) -> PcbOrder:
    """
    Creates and saves a PcbOrder record to the database after a successful payment.

    Args:
        db (Session): The SQLAlchemy database session.
        user (User): The authenticated user placing the order.
        payment_details (Dict): The Stripe checkout session object.
        manufacturing_params (Dict): The manufacturing parameters from Stripe metadata.

    Returns:
        PcbOrder: The newly created PcbOrder object.
    """
    logger.info(f"Creating PCB order record for Stripe Payment Intent: {payment_details.get('payment_intent')}")
    
    new_pcb_order = PcbOrder(
        user_id=user.id,
        order_number=f"PCB-{payment_details['id'][-10:].upper()}",
        status=OrderStatus.PROCESSING,
        width_mm=float(width_mm),
        height_mm=float(height_mm),
        final_price_egp=payment_details['amount_total'] / 100.0,
        stripe_payment_intent_id=payment_details.get('payment_intent'),
        base_material=manufacturing_params.get("base_material", "N/A"),
        manufacturing_parameters=manufacturing_params # Store the full dictionary
    )
    
    db.add(new_pcb_order)
    # The commit will happen in the webhook handler after all operations.
    logger.info(f"Successfully created PCB Order object {new_pcb_order.order_number}")
    return new_pcb_order