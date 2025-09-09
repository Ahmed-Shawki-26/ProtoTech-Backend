"""
Cart Validation Service
Provides comprehensive validation for e-commerce cart operations
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from ..services.odoo_service import get_product_by_id

logger = logging.getLogger(__name__)

# Cart validation constants
MAX_QUANTITY_PER_ITEM = 100
MAX_CART_TOTAL = 100000  # EGP
MAX_ITEMS_IN_CART = 50
CART_EXPIRATION_HOURS = 24
MIN_QUANTITY = 1

class CartValidationService:
    """Service for validating cart operations"""
    
    @staticmethod
    async def validate_cart_item(item: Dict[str, Any]) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
        """
        Validate a single cart item
        
        Returns:
            Tuple of (is_valid, errors, updated_item)
        """
        errors = []
        
        # Basic validation
        item_id = item.get('id')
        quantity = int(item.get('quantity', 1))
        price = float(item.get('price', 0))
        name = item.get('name', 'Unknown Product')
        
        if not item_id:
            errors.append("Item ID is required")
            return False, errors, None
            
        if quantity < MIN_QUANTITY:
            errors.append(f"Quantity must be at least {MIN_QUANTITY}")
            return False, errors, None
            
        if quantity > MAX_QUANTITY_PER_ITEM:
            errors.append(f"Maximum quantity allowed is {MAX_QUANTITY_PER_ITEM}")
            return False, errors, None
            
        if price <= 0:
            errors.append("Price must be greater than 0")
            return False, errors, None
        
        # Validate Odoo products
        if item_id.isdigit():
            try:
                product_data = await get_product_by_id(int(item_id))
                if not product_data:
                    errors.append(f"Product {name} is no longer available")
                    return False, errors, None
                
                available_stock = product_data.get('qty_available', 0)
                current_price = product_data.get('list_price', 0)
                
                # Check stock availability
                if available_stock < quantity:
                    errors.append(f"Only {available_stock} units available for {name}")
                
                # Check price changes
                if abs(current_price - price) > 0.01:
                    errors.append(f"Price for {name} has changed from {price} to {current_price} EGP")
                
                # Create updated item with current data
                updated_item = {
                    **item,
                    'price': current_price,
                    'stock': available_stock,
                    'maxQuantity': min(available_stock, MAX_QUANTITY_PER_ITEM),
                    'lastValidated': datetime.utcnow().isoformat(),
                    'isStockValid': available_stock >= quantity,
                    'isPriceValid': abs(current_price - price) <= 0.01,
                    'status': 'Out of Stock' if available_stock <= 0 else 'Limited Stock' if available_stock < quantity else 'In Stock',
                    'statusColor': 'text-red-600' if available_stock <= 0 else 'text-yellow-600' if available_stock < quantity else 'text-emerald-600'
                }
                
                return len(errors) == 0, errors, updated_item
                
            except Exception as e:
                logger.error(f"Error validating Odoo product {item_id}: {e}")
                errors.append(f"Failed to validate {name}")
                return False, errors, None
        else:
            # Custom manufacturing products (PCB, 3D printing)
            # No stock validation needed, but check other limits
            updated_item = {
                **item,
                'lastValidated': datetime.utcnow().isoformat(),
                'isStockValid': True,
                'isPriceValid': True,
                'status': 'Available',
                'statusColor': 'text-emerald-600'
            }
            
            return len(errors) == 0, errors, updated_item
    
    @staticmethod
    async def validate_cart(items: List[Dict[str, Any]]) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """
        Validate entire cart
        
        Returns:
            Tuple of (is_valid, errors, validated_items)
        """
        errors = []
        validated_items = []
        total_value = 0.0
        
        # Check cart limits
        if len(items) > MAX_ITEMS_IN_CART:
            errors.append(f"Cart cannot contain more than {MAX_ITEMS_IN_CART} different items")
            return False, errors, []
        
        total_quantity = sum(int(item.get('quantity', 1)) for item in items)
        if total_quantity > MAX_QUANTITY_PER_ITEM * MAX_ITEMS_IN_CART:
            errors.append(f"Total quantity cannot exceed {MAX_QUANTITY_PER_ITEM * MAX_ITEMS_IN_CART} items")
            return False, errors, []
        
        # Validate each item
        for item in items:
            is_valid, item_errors, updated_item = await CartValidationService.validate_cart_item(item)
            errors.extend(item_errors)
            
            if updated_item:
                validated_items.append(updated_item)
                total_value += updated_item['price'] * updated_item['quantity']
        
        # Check total cart value
        if total_value > MAX_CART_TOTAL:
            errors.append(f"Cart total cannot exceed {MAX_CART_TOTAL} EGP")
        
        return len(errors) == 0, errors, validated_items
    
    @staticmethod
    def validate_quantity_change(current_quantity: int, new_quantity: int, max_available: int = None) -> Tuple[bool, List[str]]:
        """
        Validate quantity change for an item
        
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        if new_quantity < MIN_QUANTITY:
            errors.append(f"Quantity must be at least {MIN_QUANTITY}")
            
        if new_quantity > MAX_QUANTITY_PER_ITEM:
            errors.append(f"Maximum quantity allowed is {MAX_QUANTITY_PER_ITEM}")
            
        if max_available and new_quantity > max_available:
            errors.append(f"Only {max_available} units available")
            
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_cart_limits(items: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate cart limits without checking stock/price
        
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        if len(items) > MAX_ITEMS_IN_CART:
            errors.append(f"Cart cannot contain more than {MAX_ITEMS_IN_CART} different items")
            
        total_quantity = sum(int(item.get('quantity', 1)) for item in items)
        if total_quantity > MAX_QUANTITY_PER_ITEM * MAX_ITEMS_IN_CART:
            errors.append(f"Total quantity cannot exceed {MAX_QUANTITY_PER_ITEM * MAX_ITEMS_IN_CART} items")
            
        total_value = sum(float(item.get('price', 0)) * int(item.get('quantity', 1)) for item in items)
        if total_value > MAX_CART_TOTAL:
            errors.append(f"Cart total cannot exceed {MAX_CART_TOTAL} EGP")
            
        return len(errors) == 0, errors
    
    @staticmethod
    def is_item_expired(item: Dict[str, Any]) -> bool:
        """
        Check if a cart item has expired
        
        Returns:
            True if item is expired, False otherwise
        """
        last_validated = item.get('lastValidated')
        if not last_validated:
            return False  # No validation timestamp, assume not expired
            
        try:
            validated_time = datetime.fromisoformat(last_validated.replace('Z', '+00:00'))
            current_time = datetime.utcnow()
            return current_time - validated_time > timedelta(hours=CART_EXPIRATION_HOURS)
        except ValueError:
            return False  # Invalid timestamp, assume not expired
    
    @staticmethod
    def get_cart_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get summary statistics for cart
        
        Returns:
            Dictionary with cart summary
        """
        total_items = sum(int(item.get('quantity', 0)) for item in items)
        total_value = sum(float(item.get('price', 0)) * int(item.get('quantity', 0)) for item in items)
        
        # Count items by category
        category_counts = {}
        for item in items:
            category = item.get('category', 'Unknown')
            category_counts[category] = category_counts.get(category, 0) + int(item.get('quantity', 0))
        
        # Count items by validation status
        stock_valid_count = sum(1 for item in items if item.get('isStockValid', True))
        price_valid_count = sum(1 for item in items if item.get('isPriceValid', True))
        expired_count = sum(1 for item in items if CartValidationService.is_item_expired(item))
        
        return {
            'total_items': total_items,
            'total_value': total_value,
            'item_count': len(items),
            'category_counts': category_counts,
            'stock_valid_count': stock_valid_count,
            'price_valid_count': price_valid_count,
            'expired_count': expired_count,
            'last_updated': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def filter_expired_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out expired items from cart
        
        Returns:
            List of non-expired items
        """
        return [item for item in items if not CartValidationService.is_item_expired(item)]
    
    @staticmethod
    def merge_carts(user_cart: List[Dict[str, Any]], guest_cart: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge user cart with guest cart
        
        Returns:
            Merged cart items
        """
        merged_items = user_cart.copy()
        existing_ids = {item.get('id') for item in user_cart}
        
        for guest_item in guest_cart:
            item_id = guest_item.get('id')
            if item_id not in existing_ids:
                merged_items.append(guest_item)
            else:
                # Update quantity if item exists
                for user_item in merged_items:
                    if user_item.get('id') == item_id:
                        current_qty = int(user_item.get('quantity', 0))
                        guest_qty = int(guest_item.get('quantity', 0))
                        new_qty = current_qty + guest_qty
                        
                        # Check quantity limits
                        if new_qty > MAX_QUANTITY_PER_ITEM:
                            new_qty = MAX_QUANTITY_PER_ITEM
                        
                        user_item['quantity'] = new_qty
                        user_item['updated_at'] = datetime.utcnow().isoformat()
                        break
        
        return merged_items
