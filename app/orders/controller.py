from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from ..database.core import get_db
from ..auth.service import get_current_user
# from ..schemas.user import User  # get_current_user returns TokenData, not User
from ..schemas.orders import (
    CreateOrderRequest, OrderResponse, OrderUpdateRequest, 
    OrderListResponse, OrderStatusUpdate, PaymentStatusUpdate
)
from .service import OrderService
from .models import Order
from ..auth.service import CurrentUser

router = APIRouter(prefix="/orders")

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: CreateOrderRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new order for the authenticated user"""
    try:
        order = await OrderService.create_order(db, current_user, order_data)
        return order
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )

@router.get("/", response_model=OrderListResponse)
async def get_user_orders(
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all orders for the authenticated user with pagination"""
    try:
        orders = await OrderService.get_user_orders(db, str(current_user.user_id), skip, limit)
        total = len(orders)  # In production, you'd want a separate count query
        
        return OrderListResponse(
            orders=orders,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve orders: {str(e)}"
        )

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific order by ID (user can only see their own orders)"""
    try:
        order = await OrderService.get_order_by_id(db, order_id, str(current_user.user_id))
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order: {str(e)}"
        )

@router.get("/number/{order_number}", response_model=OrderResponse)
async def get_order_by_number(
    order_number: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get order by order number"""
    try:
        order = await OrderService.get_order_by_number(db, order_number, str(current_user.user_id))
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order: {str(e)}"
        )

@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    status_update: OrderStatusUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update order status"""
    try:
        order = await OrderService.update_order_status(
            db, order_id, str(current_user.user_id), status_update.status
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update order status: {str(e)}"
        )

@router.put("/{order_id}/payment-status", response_model=OrderResponse)
async def update_payment_status(
    order_id: str,
    payment_update: PaymentStatusUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update payment status"""
    try:
        order = await OrderService.update_payment_status(
            db, order_id, payment_update.payment_status,
            payment_update.stripe_session_id,
            payment_update.stripe_payment_intent_id
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment status: {str(e)}"
        )

@router.put("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an order (only if it's in pending or confirmed status)"""
    try:
        order = await OrderService.cancel_order(db, order_id, str(current_user.user_id))
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or cannot be cancelled"
            )
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )

# Admin endpoints (for future use)
@router.get("/admin/all", response_model=List[OrderResponse])
async def get_all_orders(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all orders (admin only - implement admin check later)"""
    try:
        # TODO: Add admin role check
        orders = db.query(Order).offset(skip).limit(limit).all()
        return orders
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve orders: {str(e)}"
        )

@router.get("/tracking/{order_id}", response_model=OrderResponse)
async def get_order_tracking(
    order_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get order tracking information by order ID"""
    try:
        order = await OrderService.get_order_by_id(db, order_id, str(current_user.user_id))
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        return order
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order tracking: {str(e)}"
        )

@router.get("/statistics")
async def get_order_statistics(
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Get order statistics for the current user"""
    try:
        stats = await OrderService.get_order_statistics(db, str(current_user.user_id))
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order statistics: {str(e)}"
        )

@router.get("/by-status/{status}")
async def get_orders_by_status(
    status: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get orders filtered by status"""
    try:
        orders = await OrderService.get_orders_by_status(db, str(current_user.user_id), status, skip, limit)
        return orders
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orders by status: {str(e)}"
        )

@router.get("/track/{order_id}")
async def track_order(
    order_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Get order tracking information for a specific order."""
    try:
        tracking_info = await OrderService.get_order_tracking_info(db, order_id, str(current_user.user_id))
        
        if not tracking_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or you don't have permission to view it"
            )
        
        return {
            "success": True,
            "tracking_info": tracking_info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order tracking info: {str(e)}"
        )

@router.get("/user/{user_id}")
async def get_user_orders(
    user_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db)
):
    """Get all orders for a specific user."""
    try:
        # Ensure user can only view their own orders
        if str(current_user.user_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own orders"
            )
        
        orders = await OrderService.get_user_orders(db, user_id)
        
        return {
            "success": True,
            "orders": [
                {
                    "id": str(order.id),
                    "order_number": order.order_number,
                    "total_amount": order.total_amount,
                    "status": order.status,
                    "payment_status": order.payment_status,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "updated_at": order.updated_at.isoformat() if order.updated_at else None
                }
                for order in orders
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user orders: {str(e)}"
        )
