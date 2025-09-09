from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
from .models import Order, OrderItem
from ..schemas.user import User
from ..schemas.orders import CreateOrderRequest, OrderResponse, OrderUpdateRequest
from sqlalchemy import func

class OrderService:
    
    @staticmethod
    async def create_order(db: Session, user: User, order_data: CreateOrderRequest) -> Order:
        """Create a new order for a user"""
        # Generate unique order number
        order_number = f"PT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create order
        order = Order(
            user_id=user.id,
            order_number=order_number,
            cart_items=order_data.items,  # Updated to use new column name
            total_amount=order_data.total_amount,
            shipping_address=order_data.shipping_address,
            billing_address=order_data.billing_address,
            shipping_cost=order_data.shipping_cost or 0.0,
            tax_amount=order_data.tax_amount or 0.0,
            discount_amount=order_data.discount_amount or 0.0,
            notes=order_data.notes,
            shipping_method=order_data.shipping_method
        )
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        # Create order items
        for item_data in order_data.items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item_data.get("id"),
                product_name=item_data.get("name"),
                quantity=item_data.get("quantity"),
                unit_price=item_data.get("price"),
                total_price=item_data.get("price") * item_data.get("quantity"),
                product_data=item_data
            )
            db.add(order_item)
        
        db.commit()
        return order
    
    @staticmethod
    async def get_order_by_id(db: Session, order_id: str, user_id: str) -> Optional[Order]:
        """Get a specific order by ID (user can only see their own orders)"""
        return db.query(Order).filter(
            and_(Order.id == order_id, Order.user_id == user_id)
        ).first()
    
    @staticmethod
    async def get_user_orders(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Order]:
        """Get all orders for a specific user with pagination"""
        return db.query(Order).filter(Order.user_id == user_id)\
                 .order_by(Order.created_at.desc())\
                 .offset(skip).limit(limit).all()
    
    @staticmethod
    async def get_order_by_number(db: Session, order_number: str, user_id: str) -> Optional[Order]:
        """Get order by order number"""
        return db.query(Order).filter(
            and_(Order.order_number == order_number, Order.user_id == user_id)
        ).first()
    
    @staticmethod
    async def update_order_status(db: Session, order_id: str, user_id: str, status: str) -> Optional[Order]:
        """Update order status"""
        order = await OrderService.get_order_by_id(db, order_id, user_id)
        if order:
            order.status = status
            order.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(order)
        return order
    
    @staticmethod
    async def update_payment_status(db: Session, order_id: str, payment_status: str, 
                                 stripe_session_id: str = None, stripe_payment_intent_id: str = None) -> Optional[Order]:
        """Update payment status (can be called by webhook)"""
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            order.payment_status = payment_status
            if stripe_session_id:
                order.stripe_session_id = stripe_session_id
            if stripe_payment_intent_id:
                order.stripe_payment_intent_id = stripe_payment_intent_id
            order.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(order)
        return order
    
    @staticmethod
    async def get_order_by_stripe_session(db: Session, stripe_session_id: str) -> Optional[Order]:
        """Get order by Stripe session ID (for webhook processing)"""
        return db.query(Order).filter(Order.stripe_session_id == stripe_session_id).first()
    
    @staticmethod
    async def cancel_order(db: Session, order_id: str, user_id: str) -> Optional[Order]:
        """Cancel an order (only if it's in pending or confirmed status)"""
        order = await OrderService.get_order_by_id(db, order_id, user_id)
        if order and order.status in ["pending", "confirmed"]:
            order.status = "cancelled"
            order.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(order)
        return order

    @staticmethod
    async def get_order_tracking_info(db: Session, order_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get order tracking information"""
        order = await OrderService.get_order_by_id(db, order_id, user_id)
        if not order:
            return None
        
        # Calculate estimated delivery date based on order date and shipping method
        estimated_delivery = None
        if order.created_at:
            delivery_days = 7 if order.shipping_method == "standard" else 3
            estimated_delivery = order.created_at + timedelta(days=delivery_days)
        
        return {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "tracking_number": order.tracking_number,
            "shipping_method": order.shipping_method,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "estimated_delivery": estimated_delivery.isoformat() if estimated_delivery else None,
            "total_amount": order.total_amount,
            "shipping_address": order.shipping_address,
            "items": order.cart_items
        }

    @staticmethod
    async def update_order_tracking(db: Session, order_id: str, tracking_number: str, status: str = None) -> Optional[Order]:
        """Update order tracking information (admin function)"""
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            order.tracking_number = tracking_number
            if status:
                order.status = status
            order.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(order)
        return order

    @staticmethod
    async def get_orders_by_status(db: Session, user_id: str, status: str = None, skip: int = 0, limit: int = 100) -> List[Order]:
        """Get orders filtered by status"""
        query = db.query(Order).filter(Order.user_id == user_id)
        if status:
            query = query.filter(Order.status == status)
        return query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    async def get_order_statistics(db: Session, user_id: str) -> Dict[str, Any]:
        """Get order statistics for a user"""
        total_orders = db.query(Order).filter(Order.user_id == user_id).count()
        pending_orders = db.query(Order).filter(Order.user_id == user_id, Order.status == "pending").count()
        processing_orders = db.query(Order).filter(Order.user_id == user_id, Order.status == "processing").count()
        shipped_orders = db.query(Order).filter(Order.user_id == user_id, Order.status == "shipped").count()
        delivered_orders = db.query(Order).filter(Order.user_id == user_id, Order.status == "delivered").count()
        cancelled_orders = db.query(Order).filter(Order.user_id == user_id, Order.status == "cancelled").count()
        
        total_spent = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.payment_status == "paid"
        ).with_entities(func.sum(Order.total_amount)).scalar() or 0.0
        
        return {
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "processing_orders": processing_orders,
            "shipped_orders": shipped_orders,
            "delivered_orders": delivered_orders,
            "cancelled_orders": cancelled_orders,
            "total_spent": float(total_spent)
        }
