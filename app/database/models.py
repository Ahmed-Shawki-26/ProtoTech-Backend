# Central models file to avoid circular imports
# Import order is critical: Order and UserCart first, then User

from .core import Base

# Import Order and UserCart models first
from ..orders.models import Order, OrderItem
from ..cart.models import UserCart

# Import User model last (after Order and UserCart are defined)
from ..schemas.user import User

# Export all models
__all__ = [
    "Base",
    "Order", 
    "OrderItem",
    "UserCart",
    "User"
]

