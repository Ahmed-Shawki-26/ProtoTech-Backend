# app/pcb_orders/service.py
# Service for managing PCB orders

import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .models import PcbOrder, PcbOrderStatus
from ..schemas.pcb import ManufacturingParameters, BoardDimensions

class PcbOrderService:
    """Service for managing PCB orders"""
    
    @staticmethod
    def create_pcb_order(
        db: Session,
        user_id: str,
        order_number: str,
        dimensions: BoardDimensions,
        manufacturing_params: ManufacturingParameters,
        final_price_egp: float,
        stripe_payment_intent_id: Optional[str] = None
    ) -> PcbOrder:
        """
        Create a new PCB order
        
        Args:
            db: Database session
            user_id: User ID
            order_number: Unique order number
            dimensions: PCB dimensions
            manufacturing_params: Manufacturing parameters
            final_price_egp: Final price in EGP
            stripe_payment_intent_id: Optional Stripe payment intent ID
            
        Returns:
            Created PcbOrder instance
        """
        
        # Convert manufacturing parameters to dict
        manufacturing_params_dict = manufacturing_params.model_dump()
        
        pcb_order = PcbOrder(
            user_id=uuid.UUID(user_id),
            order_number=order_number,
            width_mm=dimensions.width_mm,
            height_mm=dimensions.height_mm,
            final_price_egp=final_price_egp,
            stripe_payment_intent_id=stripe_payment_intent_id,
            base_material=manufacturing_params.base_material,
            manufacturing_parameters=manufacturing_params_dict,
            status=PcbOrderStatus.PENDING
        )
        
        db.add(pcb_order)
        db.commit()
        db.refresh(pcb_order)
        
        return pcb_order
    
    @staticmethod
    def get_pcb_order_by_id(db: Session, order_id: str) -> Optional[PcbOrder]:
        """Get PCB order by ID"""
        return db.query(PcbOrder).filter(PcbOrder.id == uuid.UUID(order_id)).first()
    
    @staticmethod
    def get_pcb_order_by_number(db: Session, order_number: str) -> Optional[PcbOrder]:
        """Get PCB order by order number"""
        return db.query(PcbOrder).filter(PcbOrder.order_number == order_number).first()
    
    @staticmethod
    def get_user_pcb_orders(
        db: Session, 
        user_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[PcbOrder]:
        """Get PCB orders for a specific user"""
        return db.query(PcbOrder)\
            .filter(PcbOrder.user_id == uuid.UUID(user_id))\
            .order_by(desc(PcbOrder.created_at))\
            .offset(offset)\
            .limit(limit)\
            .all()
    
    @staticmethod
    def update_pcb_order_status(
        db: Session, 
        order_id: str, 
        status: PcbOrderStatus
    ) -> Optional[PcbOrder]:
        """Update PCB order status"""
        pcb_order = db.query(PcbOrder).filter(PcbOrder.id == uuid.UUID(order_id)).first()
        
        if pcb_order:
            pcb_order.status = status
            db.commit()
            db.refresh(pcb_order)
        
        return pcb_order
    
    @staticmethod
    def update_pcb_order_payment(
        db: Session,
        order_id: str,
        stripe_payment_intent_id: str,
        status: PcbOrderStatus = PcbOrderStatus.PROCESSING
    ) -> Optional[PcbOrder]:
        """Update PCB order payment information"""
        pcb_order = db.query(PcbOrder).filter(PcbOrder.id == uuid.UUID(order_id)).first()
        
        if pcb_order:
            pcb_order.stripe_payment_intent_id = stripe_payment_intent_id
            pcb_order.status = status
            db.commit()
            db.refresh(pcb_order)
        
        return pcb_order
    
    @staticmethod
    def get_pcb_orders_by_status(
        db: Session,
        status: PcbOrderStatus,
        limit: int = 50,
        offset: int = 0
    ) -> List[PcbOrder]:
        """Get PCB orders by status"""
        return db.query(PcbOrder)\
            .filter(PcbOrder.status == status)\
            .order_by(desc(PcbOrder.created_at))\
            .offset(offset)\
            .limit(limit)\
            .all()
    
    @staticmethod
    def get_pcb_orders_by_material(
        db: Session,
        base_material: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[PcbOrder]:
        """Get PCB orders by base material"""
        return db.query(PcbOrder)\
            .filter(PcbOrder.base_material == base_material)\
            .order_by(desc(PcbOrder.created_at))\
            .offset(offset)\
            .limit(limit)\
            .all()
    
    @staticmethod
    def get_pcb_order_statistics(db: Session) -> Dict[str, Any]:
        """Get PCB order statistics"""
        
        # Total orders
        total_orders = db.query(PcbOrder).count()
        
        # Orders by status
        status_counts = {}
        for status in PcbOrderStatus:
            count = db.query(PcbOrder).filter(PcbOrder.status == status).count()
            status_counts[status.value] = count
        
        # Orders by material
        material_counts = {}
        materials = db.query(PcbOrder.base_material).distinct().all()
        for material_tuple in materials:
            material = material_tuple[0]
            count = db.query(PcbOrder).filter(PcbOrder.base_material == material).count()
            material_counts[material] = count
        
        # Average order value
        avg_price_result = db.query(db.func.avg(PcbOrder.final_price_egp)).scalar()
        avg_price = float(avg_price_result) if avg_price_result else 0.0
        
        # Total revenue
        total_revenue_result = db.query(db.func.sum(PcbOrder.final_price_egp)).scalar()
        total_revenue = float(total_revenue_result) if total_revenue_result else 0.0
        
        return {
            "total_orders": total_orders,
            "orders_by_status": status_counts,
            "orders_by_material": material_counts,
            "average_order_value_egp": round(avg_price, 2),
            "total_revenue_egp": round(total_revenue, 2)
        }
    
    @staticmethod
    def delete_pcb_order(db: Session, order_id: str) -> bool:
        """Delete a PCB order"""
        pcb_order = db.query(PcbOrder).filter(PcbOrder.id == uuid.UUID(order_id)).first()
        
        if pcb_order:
            db.delete(pcb_order)
            db.commit()
            return True
        
        return False
