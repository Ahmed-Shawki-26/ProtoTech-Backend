# /src/users/controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database.core import get_db
from ..auth.service import CurrentUser
from ..auth.service import get_current_user
from .service import UserService
from ..schemas.user import ShippingAddressUpdate, ShippingAddressResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/shipping-address", response_model=ShippingAddressResponse)
async def get_default_shipping_address(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's default shipping address"""
    try:
        shipping_address = UserService.get_default_shipping_address(db, str(current_user.user_id))
        if not shipping_address:
            # Return empty response if no default address is set
            return ShippingAddressResponse()
        return shipping_address
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve shipping address: {str(e)}"
        )


@router.put("/shipping-address", response_model=ShippingAddressResponse)
async def update_default_shipping_address(
    shipping_data: ShippingAddressUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's default shipping address"""
    try:
        updated_address = UserService.update_default_shipping_address(
            db, 
            str(current_user.user_id), 
            shipping_data
        )
        if not updated_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return updated_address
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update shipping address: {str(e)}"
        )