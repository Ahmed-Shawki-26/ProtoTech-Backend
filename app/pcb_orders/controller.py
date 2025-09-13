# app/pcb_orders/controller.py
# API controller for PCB orders

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..database.core import get_db
from ..auth.service import get_current_user
from ..users.models import User
from .models import PcbOrder, PcbOrderStatus
from .service import PcbOrderService
from ..schemas.pcb import ManufacturingParameters, BoardDimensions

router = APIRouter()

# Pydantic schemas for API requests/responses
from pydantic import BaseModel
from typing import Dict, Any

class PcbOrderCreateRequest(BaseModel):
    order_number: str
    width_mm: float
    height_mm: float
    manufacturing_params: Dict[str, Any]
    final_price_egp: float
    stripe_payment_intent_id: Optional[str] = None

class PcbOrderResponse(BaseModel):
    id: str
    user_id: str
    order_number: str
    status: str
    width_mm: float
    height_mm: float
    final_price_egp: float
    stripe_payment_intent_id: Optional[str]
    base_material: str
    manufacturing_parameters: Dict[str, Any]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True

class PcbOrderUpdateRequest(BaseModel):
    status: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None

class PcbOrderStatisticsResponse(BaseModel):
    total_orders: int
    orders_by_status: Dict[str, int]
    orders_by_material: Dict[str, int]
    average_order_value_egp: float
    total_revenue_egp: float

@router.post("/", response_model=PcbOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_pcb_order(
    request: PcbOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new PCB order"""
    try:
        # Create BoardDimensions object
        dimensions = BoardDimensions(
            width_mm=request.width_mm,
            height_mm=request.height_mm,
            area_m2=(request.width_mm * request.height_mm) / 1000000.0
        )
        
        # Create ManufacturingParameters object
        manufacturing_params = ManufacturingParameters(**request.manufacturing_params)
        
        # Create PCB order
        pcb_order = PcbOrderService.create_pcb_order(
            db=db,
            user_id=str(current_user.user_id),
            order_number=request.order_number,
            dimensions=dimensions,
            manufacturing_params=manufacturing_params,
            final_price_egp=request.final_price_egp,
            stripe_payment_intent_id=request.stripe_payment_intent_id
        )
        
        return PcbOrderResponse.model_validate(pcb_order)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create PCB order: {str(e)}"
        )

@router.get("/{order_id}", response_model=PcbOrderResponse)
async def get_pcb_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific PCB order by ID"""
    try:
        pcb_order = PcbOrderService.get_pcb_order_by_id(db, order_id)
        
        if not pcb_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PCB order not found"
            )
        
        # Check if user owns this order
        if str(pcb_order.user_id) != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return PcbOrderResponse.model_validate(pcb_order)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve PCB order: {str(e)}"
        )

@router.get("/", response_model=List[PcbOrderResponse])
async def get_user_pcb_orders(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get PCB orders for the current user"""
    try:
        pcb_orders = PcbOrderService.get_user_pcb_orders(
            db=db,
            user_id=str(current_user.user_id),
            limit=limit,
            offset=offset
        )
        
        return [PcbOrderResponse.model_validate(order) for order in pcb_orders]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve PCB orders: {str(e)}"
        )

@router.put("/{order_id}", response_model=PcbOrderResponse)
async def update_pcb_order(
    order_id: str,
    request: PcbOrderUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a PCB order"""
    try:
        pcb_order = PcbOrderService.get_pcb_order_by_id(db, order_id)
        
        if not pcb_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PCB order not found"
            )
        
        # Check if user owns this order
        if str(pcb_order.user_id) != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Update status if provided
        if request.status:
            try:
                status_enum = PcbOrderStatus(request.status)
                pcb_order = PcbOrderService.update_pcb_order_status(db, order_id, status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {request.status}"
                )
        
        # Update payment intent if provided
        if request.stripe_payment_intent_id:
            pcb_order = PcbOrderService.update_pcb_order_payment(
                db, order_id, request.stripe_payment_intent_id
            )
        
        return PcbOrderResponse.model_validate(pcb_order)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update PCB order: {str(e)}"
        )

@router.get("/statistics/overview", response_model=PcbOrderStatisticsResponse)
async def get_pcb_order_statistics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get PCB order statistics (admin only for now)"""
    try:
        # For now, only allow users to see their own statistics
        # In the future, you might want to add admin role checking
        
        statistics = PcbOrderService.get_pcb_order_statistics(db)
        return PcbOrderStatisticsResponse(**statistics)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )

@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pcb_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a PCB order"""
    try:
        pcb_order = PcbOrderService.get_pcb_order_by_id(db, order_id)
        
        if not pcb_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PCB order not found"
            )
        
        # Check if user owns this order
        if str(pcb_order.user_id) != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Only allow deletion of pending orders
        if pcb_order.status != PcbOrderStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending orders can be deleted"
            )
        
        success = PcbOrderService.delete_pcb_order(db, order_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete PCB order"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete PCB order: {str(e)}"
        )
