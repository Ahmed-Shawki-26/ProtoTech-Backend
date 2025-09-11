from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
from .models import UserCart
from ..users.models import User
from ..services.odoo_service import get_product_by_id
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cart validation constants
MAX_QUANTITY_PER_ITEM = 100
MAX_CART_TOTAL = 100000  # EGP
MAX_ITEMS_IN_CART = 50
CART_EXPIRATION_HOURS = 24

class CartService:
    
    @staticmethod
    def get_user_cart(db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Get user's cart items with validation"""
        try:
            cart = db.query(UserCart).filter(UserCart.user_id == user_id).first()
            if cart:
                # Filter out expired items
                current_time = datetime.utcnow()
                valid_items = []
                
                for item in cart.items:
                    item_time = item.get('added_at')
                    if item_time:
                        try:
                            added_time = datetime.fromisoformat(item_time.replace('Z', '+00:00'))
                            if current_time - added_time < timedelta(hours=CART_EXPIRATION_HOURS):
                                valid_items.append(item)
                        except ValueError:
                            # If timestamp is invalid, keep the item
                            valid_items.append(item)
                    else:
                        # If no timestamp, keep the item
                        valid_items.append(item)
                
                # Update cart with valid items only
                if len(valid_items) != len(cart.items):
                    cart.items = valid_items
                    db.commit()
                
                return valid_items
            return []
        except Exception as e:
            logger.error(f"Error getting user cart: {e}")
            return []
    
    @staticmethod
    async def validate_cart_items(items: List[Dict[str, Any]]) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """Validate cart items for stock, price, and limits"""
        errors = []
        validated_items = []
        total_value = 0
        
        if len(items) > MAX_ITEMS_IN_CART:
            errors.append(f"Cart cannot contain more than {MAX_ITEMS_IN_CART} different items")
            return False, errors, []
        
        for item in items:
            item_errors = []
            item_id = item.get('id')
            quantity = int(item.get('quantity', 1))
            price = float(item.get('price', 0))
            
            # Check quantity limits
            if quantity <= 0:
                item_errors.append(f"Quantity must be greater than 0 for {item.get('name', 'item')}")
            elif quantity > MAX_QUANTITY_PER_ITEM:
                item_errors.append(f"Maximum quantity allowed is {MAX_QUANTITY_PER_ITEM} for {item.get('name', 'item')}")
            
            # Check price
            if price <= 0:
                item_errors.append(f"Invalid price for {item.get('name', 'item')}")
            
            # Validate Odoo products
            if item_id and item_id.isdigit():
                try:
                    product_data = await get_product_by_id(int(item_id))
                    if not product_data:
                        item_errors.append(f"Product {item.get('name', 'item')} is no longer available")
                    else:
                        available_stock = product_data.get('qty_available', 0)
                        current_price = product_data.get('list_price', 0)
                        
                        # Check stock
                        if available_stock < quantity:
                            item_errors.append(f"Only {available_stock} units available for {item.get('name', 'item')}")
                        
                        # Check price changes
                        if abs(current_price - price) > 0.01:
                            item_errors.append(f"Price for {item.get('name', 'item')} has changed from {price} to {current_price} EGP")
                        
                        # Update item with current data
                        validated_item = {
                            **item,
                            'price': current_price,
                            'stock': available_stock,
                            'last_validated': datetime.utcnow().isoformat()
                        }
                        validated_items.append(validated_item)
                        total_value += current_price * quantity
                        
                except Exception as e:
                    logger.error(f"Error validating product {item_id}: {e}")
                    item_errors.append(f"Failed to validate {item.get('name', 'item')}")
            else:
                # Non-Odoo products (custom manufacturing)
                validated_items.append(item)
                total_value += price * quantity
            
            errors.extend(item_errors)
        
        # Check total cart value
        if total_value > MAX_CART_TOTAL:
            errors.append(f"Cart total cannot exceed {MAX_CART_TOTAL} EGP")
        
        return len(errors) == 0, errors, validated_items
    
    @staticmethod
    def save_user_cart(db: Session, user_id: str, items: List[Dict[str, Any]]) -> UserCart:
        """Save or update user's cart with validation"""
        try:
            # Add timestamps to items
            current_time = datetime.utcnow().isoformat()
            items_with_timestamps = []
            
            for item in items:
                item_with_timestamp = {
                    **item,
                    'added_at': item.get('added_at', current_time),
                    'updated_at': current_time
                }
                items_with_timestamps.append(item_with_timestamp)
            
            cart = db.query(UserCart).filter(UserCart.user_id == user_id).first()
            if cart:
                cart.items = items_with_timestamps
                cart.updated_at = datetime.utcnow()
            else:
                cart = UserCart(
                    user_id=user_id, 
                    items=items_with_timestamps,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(cart)
            
            db.commit()
            db.refresh(cart)
            return cart
        except Exception as e:
            logger.error(f"Error saving user cart: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def clear_user_cart(db: Session, user_id: str) -> bool:
        """Clear user's cart"""
        try:
            cart = db.query(UserCart).filter(UserCart.user_id == user_id).first()
            if cart:
                cart.items = []
                cart.updated_at = datetime.utcnow()
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error clearing user cart: {e}")
            db.rollback()
            return False
    
    @staticmethod
    async def sync_guest_cart(db: Session, user_id: str, guest_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sync guest cart with user cart with validation"""
        try:
            user_cart = CartService.get_user_cart(db, user_id)
            
            # Merge carts
            merged_items = []
            existing_ids = {item.get('id') for item in user_cart}
            
            # Add user cart items
            merged_items.extend(user_cart)
            
            # Add guest items
            for guest_item in guest_items:
                item_id = guest_item.get('id')
                if item_id not in existing_ids:
                    merged_items.append(guest_item)
                else:
                    # Update quantity if item exists
                    for user_item in merged_items:
                        if user_item.get('id') == item_id:
                            current_qty = user_item.get('quantity', 0)
                            guest_qty = guest_item.get('quantity', 0)
                            new_qty = current_qty + guest_qty
                            
                            # Check quantity limits
                            if new_qty > MAX_QUANTITY_PER_ITEM:
                                new_qty = MAX_QUANTITY_PER_ITEM
                            
                            user_item['quantity'] = new_qty
                            user_item['updated_at'] = datetime.utcnow().isoformat()
                            break
            
            # Validate merged cart
            is_valid, errors, validated_items = await CartService.validate_cart_items(merged_items)
            
            if not is_valid:
                logger.warning(f"Cart validation errors: {errors}")
                # Remove invalid items
                merged_items = validated_items
            
            # Save the merged cart
            CartService.save_user_cart(db, user_id, merged_items)
            return merged_items
            
        except Exception as e:
            logger.error(f"Error syncing guest cart: {e}")
            return []
    
    @staticmethod
    def remove_expired_items(db: Session) -> int:
        """Remove expired items from all carts"""
        try:
            current_time = datetime.utcnow()
            expired_count = 0
            
            carts = db.query(UserCart).all()
            for cart in carts:
                valid_items = []
                for item in cart.items:
                    item_time = item.get('added_at')
                    if item_time:
                        try:
                            added_time = datetime.fromisoformat(item_time.replace('Z', '+00:00'))
                            if current_time - added_time < timedelta(hours=CART_EXPIRATION_HOURS):
                                valid_items.append(item)
                            else:
                                expired_count += 1
                        except ValueError:
                            valid_items.append(item)
                    else:
                        valid_items.append(item)
                
                if len(valid_items) != len(cart.items):
                    cart.items = valid_items
                    cart.updated_at = datetime.utcnow()
            
            db.commit()
            return expired_count
            
        except Exception as e:
            logger.error(f"Error removing expired items: {e}")
            db.rollback()
            return 0
    
    @staticmethod
    def get_cart_summary(db: Session, user_id: str) -> Dict[str, Any]:
        """Get cart summary with validation status"""
        try:
            items = CartService.get_user_cart(db, user_id)
            
            total_items = sum(item.get('quantity', 0) for item in items)
            total_value = sum(item.get('price', 0) * item.get('quantity', 0) for item in items)
            
            # Count items by category
            category_counts = {}
            for item in items:
                category = item.get('category', 'Unknown')
                category_counts[category] = category_counts.get(category, 0) + item.get('quantity', 0)
            
            return {
                'total_items': total_items,
                'total_value': total_value,
                'item_count': len(items),
                'category_counts': category_counts,
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting cart summary: {e}")
            return {
                'total_items': 0,
                'total_value': 0,
                'item_count': 0,
                'category_counts': {},
                'last_updated': datetime.utcnow().isoformat()
            }
