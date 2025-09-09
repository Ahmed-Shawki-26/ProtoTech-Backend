from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from ..database.core import get_db
from ..auth.service import get_current_user, CurrentUser
from .service import CartService

router = APIRouter(prefix="/cart")

class CartSyncRequest(BaseModel):
    items: List[Dict[str, Any]]
    user_id: str

class CartSaveRequest(BaseModel):
    items: List[Dict[str, Any]]

class CartResponse(BaseModel):
    items: List[Dict[str, Any]]
    success: bool
    message: str

class CartValidationResponse(BaseModel):
    isValid: bool
    errors: List[str]
    validated_items: List[Dict[str, Any]]
    summary: Dict[str, Any]

class CartSummaryResponse(BaseModel):
    total_items: int
    total_value: float
    item_count: int
    category_counts: Dict[str, int]
    last_updated: str

@router.get("/", response_model=CartResponse)
async def get_user_cart(
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Get user's saved cart"""
    try:
        items = CartService.get_user_cart(db, str(current_user.user_id))
        return CartResponse(
            items=items,
            success=True,
            message="Cart retrieved successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cart: {str(e)}"
        )

# Add missing cart endpoints that frontend expects

@router.post("/save", response_model=CartResponse)
async def save_user_cart(
    cart_data: CartSaveRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Save user's cart with validation"""
    try:
        # Validate cart items before saving
        is_valid, errors, validated_items = await CartService.validate_cart_items(cart_data.items)
        
        if not is_valid:
            # Save only valid items
            CartService.save_user_cart(db, str(current_user.user_id), validated_items)
            return CartResponse(
                items=validated_items,
                success=True,
                message=f"Cart saved with warnings: {', '.join(errors)}"
            )
        
        CartService.save_user_cart(db, str(current_user.user_id), cart_data.items)
        return CartResponse(
            items=cart_data.items,
            success=True,
            message="Cart saved successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save cart: {str(e)}"
        )

@router.post("/sync", response_model=CartResponse)
async def sync_guest_cart(
    cart_data: CartSyncRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Sync guest cart with user account"""
    try:
        merged_items = await CartService.sync_guest_cart(db, str(current_user.user_id), cart_data.items)
        return CartResponse(
            items=merged_items,
            success=True,
            message="Cart synchronized successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync cart: {str(e)}"
        )

@router.delete("/clear", response_model=CartResponse)
async def clear_user_cart(
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Clear user's cart"""
    try:
        success = CartService.clear_user_cart(db, str(current_user.user_id))
        return CartResponse(
            items=[],
            success=success,
            message="Cart cleared successfully" if success else "Cart was already empty"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cart: {str(e)}"
        )

@router.post("/validate", response_model=CartValidationResponse)
async def validate_cart(
    cart_data: CartSaveRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Validate cart items for stock, price, and limits"""
    try:
        is_valid, errors, validated_items = await CartService.validate_cart_items(cart_data.items)
        summary = CartService.get_cart_summary(db, str(current_user.user_id))
        
        return CartValidationResponse(
            isValid=is_valid,
            errors=errors,
            validated_items=validated_items,
            summary=summary
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate cart: {str(e)}"
        )

@router.get("/summary", response_model=CartSummaryResponse)
async def get_cart_summary(
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Get cart summary with validation status"""
    try:
        summary = CartService.get_cart_summary(db, str(current_user.user_id))
        return CartSummaryResponse(**summary)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cart summary: {str(e)}"
        )

@router.post("/refresh", response_model=CartResponse)
async def refresh_cart(
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Refresh cart with current stock and prices"""
    try:
        # Get current cart
        current_items = CartService.get_user_cart(db, str(current_user.user_id))
        
        # Validate and update items
        is_valid, errors, validated_items = await CartService.validate_cart_items(current_items)
        
        # Save updated cart
        CartService.save_user_cart(db, str(current_user.user_id), validated_items)
        
        return CartResponse(
            items=validated_items,
            success=True,
            message=f"Cart refreshed successfully. {len(errors)} items updated." if errors else "Cart refreshed successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh cart: {str(e)}"
        )

@router.delete("/expired", response_model=Dict[str, Any])
async def remove_expired_items(
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Remove expired items from user's cart"""
    try:
        # This endpoint removes expired items from all carts (admin function)
        # In a real implementation, you might want to restrict this to admins
        expired_count = CartService.remove_expired_items(db)
        
        return {
            "success": True,
            "message": f"Removed {expired_count} expired items from all carts",
            "expired_count": expired_count
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove expired items: {str(e)}"
        )
