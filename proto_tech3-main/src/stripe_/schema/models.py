from pydantic import BaseModel, Field, conint
from typing import List

# --- NEW: A model to represent a single item in the cart ---
class CartItem(BaseModel):
    odoo_product_id: int = Field(..., description="The ID of the product in Odoo.")
    quantity: conint(gt=0) = Field(..., description="The quantity being purchased.")

# --- REVISED: The main checkout request now takes a list of cart items ---
class CheckoutRequest(BaseModel):
    # The client no longer sends individual fields, just a list of what's in the cart.
    cart_items: List[CartItem] = Field(..., description="A list of items in the shopping cart.")