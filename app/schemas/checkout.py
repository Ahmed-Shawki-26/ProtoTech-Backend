from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Annotated
from datetime import datetime

class CheckoutRequest(BaseModel):
    """Request model for creating a checkout session"""
    price: Annotated[int, Field(gt=0)] = Field(..., description="Price in cents, must be greater than 0")
    customer_id: str = Field(..., description="ID of user who is paying")
    customer_email: str = Field(..., description="Email of customer who is paying")
    customer_phone: Optional[str] = Field(None, description="Phone number of customer")
    items: List[Dict[str, Any]] = Field(..., description="List of cart items to purchase")
    currency: str = Field("usd", description="Currency for the payment")
    success_url: Optional[str] = Field(None, description="Custom success URL")
    cancel_url: Optional[str] = Field(None, description="Custom cancel URL")

class CheckoutResponse(BaseModel):
    """Response model for checkout session creation"""
    url: str = Field(..., description="Stripe checkout session URL")
    session_id: str = Field(..., description="Stripe session ID")
    success: bool = Field(True, description="Operation success status")
    message: str = Field("Checkout session created successfully", description="Response message")

class PaymentConfirmation(BaseModel):
    """Model for payment confirmation data"""
    order_id: str = Field(..., description="Order ID")
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")
    amount: int = Field(..., description="Amount paid in cents")
    currency: str = Field(..., description="Payment currency")
    status: str = Field(..., description="Payment status")
    customer_email: str = Field(..., description="Customer email")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_phone: Optional[str] = Field(None, description="Customer phone number")
    created_at: datetime = Field(..., description="Payment timestamp")

class WebhookEvent(BaseModel):
    """Model for webhook event data"""
    event_type: str = Field(..., description="Type of webhook event")
    event_id: str = Field(..., description="Stripe event ID")
    data: Dict[str, Any] = Field(..., description="Event data")
    created_at: datetime = Field(..., description="Event timestamp")
