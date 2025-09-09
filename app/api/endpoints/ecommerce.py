# app/api/endpoints/ecommerce.py

from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks, Depends
from typing import List, Optional
from starlette import status
import xmlrpc.client
import os
from functools import lru_cache
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from ...database.core import get_db
from ...auth.service import get_current_user
from ...schemas.checkout import CheckoutRequest, CheckoutResponse
from ...services.stripe_service import create_checkout_session, handle_webhook_event, verify_webhook_signature, _update_inventory_after_purchase, _clear_user_cart, _create_order_from_session, _rollback_payment_processing
from ...services.odoo_service import get_product_by_id
import logging

logger = logging.getLogger(__name__)

load_dotenv()

router = APIRouter()

# Enable mock mode via env variable so frontend works without Odoo
ECOMMERCE_MOCK = os.getenv("ECOMMERCE_MOCK", "0") == "1"

# --- Mock data helpers (used when ECOMMERCE_MOCK=1) ---
def _mock_products() -> list:
    return [
        {
            "id": 1,
            "name": "Test Product 1",
            "qty_available": 10.0,
            "list_price": 29.99,
            "default_code": "TEST001",
            "description_sale": "This is a test product",
            "barcode": "123456789",
            "type": "consu",
            "image_url": None,
            "categ_id": {"id": 1, "name": "Test Category"},
            "uom_id": {"id": 1, "name": "Units"}
        },
        {
            "id": 2,
            "name": "Test Product 2",
            "qty_available": 5.0,
            "list_price": 49.99,
            "default_code": "TEST002",
            "description_sale": "Another test product",
            "barcode": "987654321",
            "type": "consu",
            "image_url": None,
            "categ_id": {"id": 1, "name": "Test Category"},
            "uom_id": {"id": 1, "name": "Units"}
        }
    ]

def _mock_get_products(limit: int, offset: int) -> list:
    data = _mock_products()
    return data[offset: offset + limit]

def _mock_get_product_by_id(product_id: int):
    for p in _mock_products():
        if p["id"] == product_id:
            return p
    return None

def _mock_categories() -> list:
    return [
        {"id": 1, "name": "Test Category", "parent_id": None, "product_count": 2}
    ]
# --- End mock helpers ---

# Simple test endpoint to verify the router is working
@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify e-commerce router is working."""
    return {"message": "E-commerce router is working!", "status": "ok", "mock": ECOMMERCE_MOCK}

# Odoo Configuration
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "test")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

@lru_cache(maxsize=1)
def get_odoo_client():
    """Connects to Odoo and authenticates, returning the UID and models proxy."""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        if not uid:
            raise ConnectionError("Odoo authentication failed. Check credentials.")
        return uid, models
    except Exception as e:
        raise ConnectionError(f"Could not connect to or authenticate with Odoo: {e}")

def execute_odoo_kw(model_name: str, method: str, args: List = None, kwargs: dict = None):
    """A generic wrapper to execute a keyword method on an Odoo model."""
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
        
    try:
        uid, models = get_odoo_client()
        result = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            model_name, method,
            args,
            kwargs
        )
        return result
    except Exception as e:
        raise ValueError(f"Odoo API Error: {e}")

def process_product_data(p_in: dict) -> dict:
    """Process raw Odoo product data into frontend-friendly format."""
    p_out = {
        'id': p_in.get('id'),
        'name': p_in.get('name'),
        'qty_available': p_in.get('qty_available', 0.0),
        'list_price': p_in.get('list_price', 0.0),
        'default_code': p_in.get('default_code') or None,
        'description_sale': p_in.get('description_sale') or None,
        'barcode': p_in.get('barcode') or None,
        'type': p_in.get('type') or None,
    }
    
    # Handle image
    if p_in.get('image_1920'):
        p_out['image_url'] = f"data:image/jpeg;base64,{p_in['image_1920']}"
    else:
        p_out['image_url'] = None
    
    # Handle category
    if p_in.get('categ_id'):
        p_out['categ_id'] = {
            'id': p_in['categ_id'][0] if isinstance(p_in['categ_id'], (list, tuple)) else p_in['categ_id'],
            'name': p_in['categ_id'][1] if isinstance(p_in['categ_id'], (list, tuple)) else str(p_in['categ_id'])
        }
    else:
        p_out['categ_id'] = None
    
    # Handle unit of measure
    if p_in.get('uom_id'):
        p_out['uom_id'] = {
            'id': p_in['uom_id'][0] if isinstance(p_in['uom_id'], (list, tuple)) else p_in['uom_id'],
            'name': p_in['uom_id'][1] if isinstance(p_in['uom_id'], (list, tuple)) else str(p_in['uom_id'])
        }
    else:
        p_out['uom_id'] = None
    
    return p_out

@router.get("/products")
async def get_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get a paginated list of all available products."""
    if ECOMMERCE_MOCK:
        return _mock_get_products(limit, offset)
    try:
        domain = [['type', '=', 'consu']]
        fields = ['id', 'name', 'qty_available', 'list_price', 'default_code', 'categ_id', 'image_1920']
        args = [domain]
        kwargs = {'fields': fields, 'limit': limit, 'offset': offset}
        
        products_raw = execute_odoo_kw('product.product', 'search_read', args, kwargs)
        processed_products = [process_product_data(p) for p in products_raw]
        
        return processed_products
    except ConnectionError as e:
        if ECOMMERCE_MOCK:
            return _mock_get_products(limit, offset)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not connect to the e-commerce service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )

@router.get("/products/search")
async def search_products(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Search products by name or description."""
    if ECOMMERCE_MOCK:
        # Return mock search results
        mock_products = _mock_products()
        filtered_products = [
            p for p in mock_products 
            if q.lower() in p["name"].lower() or 
               (p.get("description_sale") and q.lower() in p["description_sale"].lower())
        ]
        return filtered_products[offset:offset + limit]
    
    try:
        domain = [
            ['type', '=', 'consu'],
            '|',
            ['name', 'ilike', f'%{q}%'],
            ['description_sale', 'ilike', f'%{q}%']
        ]
        fields = ['id', 'name', 'qty_available', 'list_price', 'default_code', 'categ_id', 'image_1920']
        args = [domain]
        kwargs = {'fields': fields, 'limit': limit, 'offset': offset}
        
        products_raw = execute_odoo_kw('product.product', 'search_read', args, kwargs)
        processed_products = [process_product_data(p) for p in products_raw]
        
        return processed_products
    except ConnectionError as e:
        if ECOMMERCE_MOCK:
            mock_products = _mock_products()
            filtered_products = [
                p for p in mock_products 
                if q.lower() in p["name"].lower() or 
                   (p.get("description_sale") and q.lower() in p["description_sale"].lower())
            ]
            return filtered_products[offset:offset + limit]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not connect to the e-commerce service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )

@router.get("/products/filter")
async def filter_products_by_price(
    min_price: float = Query(0, ge=0),
    max_price: float = Query(None, ge=0),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Filter products by price range."""
    if ECOMMERCE_MOCK:
        # Return mock filtered results
        mock_products = _mock_products()
        filtered_products = [
            p for p in mock_products 
            if p["list_price"] >= min_price and 
               (max_price is None or p["list_price"] <= max_price)
        ]
        return filtered_products[offset:offset + limit]
    
    try:
        domain = [['type', '=', 'consu'], ['list_price', '>=', min_price]]
        if max_price is not None:
            domain.append(['list_price', '<=', max_price])
        
        fields = ['id', 'name', 'qty_available', 'list_price', 'default_code', 'categ_id', 'image_1920']
        args = [domain]
        kwargs = {'fields': fields, 'limit': limit, 'offset': offset}
        
        products_raw = execute_odoo_kw('product.product', 'search_read', args, kwargs)
        processed_products = [process_product_data(p) for p in products_raw]
        
        return processed_products
    except ConnectionError as e:
        if ECOMMERCE_MOCK:
            mock_products = _mock_products()
            filtered_products = [
                p for p in mock_products 
                if p["list_price"] >= min_price and 
                   (max_price is None or p["list_price"] <= max_price)
            ]
            return filtered_products[offset:offset + limit]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not connect to the e-commerce service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )

@router.get("/products/{product_id}")
async def get_product_detail(product_id: int):
    """Get the full details for a single product by its ID."""
    if ECOMMERCE_MOCK:
        product = _mock_get_product_by_id(product_id)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return product
    try:
        domain = [['id', '=', product_id]]
        fields = [
            'id', 'name', 'description_sale', 'qty_available', 'list_price', 
            'standard_price', 'default_code', 'barcode', 'categ_id', 'uom_id',
            'type', 'image_1920'
        ]
        args = [domain]
        kwargs = {'fields': fields, 'limit': 1}
        
        products = execute_odoo_kw('product.product', 'search_read', args, kwargs)
        if not products:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        
        return process_product_data(products[0])
    except HTTPException:
        raise
    except ConnectionError as e:
        if ECOMMERCE_MOCK:
            product = _mock_get_product_by_id(product_id)
            if not product:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
            return product
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not connect to the e-commerce service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )

@router.get("/product-image/{product_id}")
async def get_product_image(product_id: int):
    """Serve product image from Odoo"""
    try:
        # Get product image from Odoo
        domain = [['id', '=', product_id]]
        fields = ['image_1920']
        args = [domain]
        kwargs = {'fields': fields, 'limit': 1}
        products = execute_odoo_kw('product.product', 'search_read', args, kwargs)
        
        if not products or not products[0].get('image_1920'):
            raise HTTPException(status_code=404, detail="Product image not found")
        
        # Decode base64 image
        import base64
        from fastapi.responses import Response
        
        image_data = base64.b64decode(products[0]['image_1920'])
        
        # Return image with proper headers
        return Response(
            content=image_data,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Content-Disposition": f"inline; filename=product_{product_id}.jpg"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving product image: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve product image")

@router.get("/categories")
async def get_categories():
    """Get a list of all product categories."""
    if ECOMMERCE_MOCK:
        return _mock_categories()
    try:
        fields = ['id', 'name', 'parent_id', 'product_count']
        args = [[]]
        kwargs = {'fields': fields}
        
        categories_raw = execute_odoo_kw('product.category', 'search_read', args, kwargs)
        
        # Process categories to handle parent_id format
        for cat in categories_raw:
            if cat.get('parent_id'):
                cat['parent_id'] = {
                    'id': cat['parent_id'][0] if isinstance(cat['parent_id'], (list, tuple)) else cat['parent_id'],
                    'name': cat['parent_id'][1] if isinstance(cat['parent_id'], (list, tuple)) else str(cat['parent_id'])
                }
        
        return categories_raw
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not connect to the e-commerce service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )

@router.get("/categories/{category_id}/products")
async def get_products_by_category(
    category_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get products by category ID."""
    if ECOMMERCE_MOCK:
        # Return mock category products
        mock_products = _mock_products()
        filtered_products = [
            p for p in mock_products 
            if p.get("categ_id", {}).get("id") == category_id
        ]
        return filtered_products[offset:offset + limit]
    
    try:
        domain = [['type', '=', 'consu'], ['categ_id', '=', category_id]]
        fields = ['id', 'name', 'qty_available', 'list_price', 'default_code', 'categ_id', 'image_1920']
        args = [domain]
        kwargs = {'fields': fields, 'limit': limit, 'offset': offset}
        
        products_raw = execute_odoo_kw('product.product', 'search_read', args, kwargs)
        processed_products = [process_product_data(p) for p in products_raw]
        
        return processed_products
    except ConnectionError as e:
        if ECOMMERCE_MOCK:
            mock_products = _mock_products()
            filtered_products = [
                p for p in mock_products 
                if p.get("categ_id", {}).get("id") == category_id
            ]
            return filtered_products[offset:offset + limit]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not connect to the e-commerce service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint for e-commerce service."""
    if ECOMMERCE_MOCK:
        return {"status": "healthy", "service": "ecommerce", "mode": "mock"}
    try:
        # Try to connect to Odoo
        get_odoo_client()
        return {"status": "healthy", "service": "ecommerce", "odoo_connection": "ok", "mode": "live"}
    except Exception as e:
        return {"status": "unhealthy", "service": "ecommerce", "odoo_connection": "error", "error": str(e), "mode": "live"}

# ===== CHECKOUT ENDPOINTS =====

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    checkout_data: CheckoutRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe checkout session for payment processing.
    Requires authentication.
    """
    try:
        # Validate that the user is the one making the request
        if str(current_user.user_id) != checkout_data.customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create checkout sessions for your own account"
            )
        
        # Calculate total price from items if not provided
        if checkout_data.price <= 0:
            total_price = sum(item.get("price", 0) * item.get("quantity", 1) for item in checkout_data.items)
            checkout_data.price = int(total_price * 100)  # Convert to cents
        
        # Create checkout session
        result = await create_checkout_session(checkout_data)
        
        return CheckoutResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhook events for payment confirmations.
    This endpoint is called by Stripe and doesn't require authentication.
    """
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        logger.info(f"Received webhook request: content-length={len(payload)}, signature={sig_header[:20] if sig_header else 'None'}...")
        
        if not sig_header:
            logger.error("Missing Stripe signature header in webhook")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe signature header"
            )
        
        # Verify webhook signature
        event = verify_webhook_signature(payload, sig_header)
        
        logger.info(f"Webhook verified successfully: event_type={event.get('type')}, event_id={event.get('id')}")
        
        # Process webhook event in background
        background_tasks.add_task(handle_webhook_event, event)
        
        logger.info(f"Webhook event queued for background processing: {event.get('type')}")
        
        return {"status": "ok", "message": "Webhook processed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        logger.exception("Full webhook error details:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )

@router.get("/payment-status/{session_id}")
async def get_payment_status(
    session_id: str,
):
    """
    Get the payment status for a specific checkout session.
    Requires authentication.
    """
    try:
        import stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        # Retrieve session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        return {
            "session_id": session.id,
            "status": session.payment_status,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "customer_email": session.customer_details.get("email") if session.customer_details else None,
            "created": session.created,
            "success_url": session.success_url,
            "cancel_url": session.cancel_url
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment status: {str(e)}"
        )

# Simple cache for order details to prevent redundant API calls
_order_details_cache = {}

@router.get("/order-details/{session_id}")
async def get_order_details(
    session_id: str,
):
    """
    Get order details for a specific checkout session.
    Requires authentication.
    """
    # Check cache first
    if session_id in _order_details_cache:
        logger.info(f"Returning cached order details for session: {session_id}")
        return _order_details_cache[session_id]
    
    try:
        import stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        # Retrieve session from Stripe with expanded line items
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["line_items.data.price.product"]
        )
        
        # Get line items from Stripe session
        order_items = []
        if session.line_items and session.line_items.data:
            for line_item in session.line_items.data:
                price = line_item.price
                product = price.product if price else None
                
                order_items.append({
                    "id": line_item.id,
                    "name": line_item.description or (product.name if product else "Unknown Product"),
                    "description": line_item.description,
                    "quantity": line_item.quantity,
                    "unit_amount": price.unit_amount if price else 0,
                    "amount_total": line_item.amount_total,
                    "amount_subtotal": line_item.amount_subtotal,
                    "currency": session.currency,
                    "price": {
                        "unit_amount": price.unit_amount if price else 0,
                        "currency": price.currency if price else session.currency,
                        "product": {
                            "id": product.id if product else None,
                            "name": product.name if product else None,
                            "images": product.images if product else [],
                            "metadata": product.metadata if product else {}
                        } if product else None
                    },
                    "image_url": product.images[0] if product and product.images else None
                })
        
        # Get customer details including phone
        customer_details = session.customer_details or {}
        customer_phone = customer_details.get("phone")
        
        # If no phone in customer_details, try to get it from metadata
        if not customer_phone:
            customer_phone = session.metadata.get("customer_phone")
        
        # Update customer_details to include phone
        if customer_phone:
            customer_details["phone"] = customer_phone
        
        result = {
            "session_id": session.id,
            "status": session.payment_status,
            "amount_total": session.amount_total,
            "amount_subtotal": session.amount_subtotal,
            "currency": session.currency,
            "customer_email": customer_details.get("email"),
            "customer_name": customer_details.get("name"),
            "customer_details": customer_details,
            "shipping_details": {
                "address": customer_details.get("address")
            },
            "created": session.created,
            "order_items": order_items,
            "order_id": f"order_{session.id}",
            "total_details": {
                "amount_tax": session.total_details.amount_tax if session.total_details else 0,
                "amount_shipping": session.total_details.amount_shipping if session.total_details else 0,
                "amount_discount": session.total_details.amount_discount if session.total_details else 0
            } if session.total_details else None
        }
        
        # Cache the result
        _order_details_cache[session_id] = result
        logger.info(f"Cached order details for session: {session_id}")
        
        return result
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order details: {str(e)}"
        )

@router.post("/complete-payment/{session_id}")
async def complete_payment(
    session_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually complete payment processing after successful Stripe payment.
    This endpoint handles cart clearing and inventory updates.
    """
    try:
        import stripe
        import logging
        logger = logging.getLogger(__name__)
        
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        # Retrieve session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Verify payment was successful
        if session.payment_status != "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment was not successful"
            )
        
        # Verify user owns this session
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id", "")
        if str(current_user.user_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only complete payments for your own orders"
            )
        
        logger.info(f"Completing payment for session {session_id}")
        
        # Track success/failure for rollback
        order_created = False
        inventory_updated = False
        cart_cleared = False
        
        try:
            # Create order in database
            logger.info("Creating order in database...")
            await _create_order_from_session(session, user_id)
            order_created = True
            logger.info("Order created successfully in database")
            
            # Update inventory in Odoo
            logger.info("Starting inventory update...")
            await _update_inventory_after_purchase(metadata)
            inventory_updated = True
            logger.info("Inventory update completed successfully")
            
            # Clear user's cart after successful payment
            logger.info(f"Starting cart clearing for user {user_id}...")
            await _clear_user_cart(user_id)
            cart_cleared = True
            logger.info(f"Cart cleared for user {user_id} after successful payment")
            
            return {
                "status": "success",
                "message": "Payment completed successfully",
                "session_id": session_id,
                "order_created": True,
                "inventory_updated": True,
                "cart_cleared": True
            }
            
        except Exception as e:
            logger.error(f"Error during payment completion: {e}")
            logger.exception("Payment completion error details:")
            
            # Rollback operations if needed
            await _rollback_payment_processing(session, user_id, order_created, inventory_updated, cart_cleared)
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to complete payment processing: {str(e)}"
            )
        
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment completion error: {e}")
        logger.exception("Payment completion error details:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete payment: {str(e)}"
        )

@router.get("/products/stock/check")
async def check_products_stock(product_ids: str = Query(..., description="Comma-separated list of product IDs")):
    """Get stock information for multiple products at once."""
    if ECOMMERCE_MOCK:
        # Return mock stock data
        ids = [int(id.strip()) for id in product_ids.split(',') if id.strip().isdigit()]
        return [{"id": id, "qty_available": 10.0} for id in ids]
    
    try:
        ids = [int(id.strip()) for id in product_ids.split(',') if id.strip().isdigit()]
        if not ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid product IDs provided"
            )
        
        domain = [['id', 'in', ids]]
        fields = ['id', 'name', 'qty_available']
        args = [domain]
        kwargs = {'fields': fields}
        
        products = execute_odoo_kw('product.product', 'search_read', args, kwargs)
        
        # Return simplified stock data
        stock_data = []
        for product in products:
            stock_data.append({
                'id': product.get('id'),
                'name': product.get('name'),
                'qty_available': product.get('qty_available', 0.0)
            })
        
        return stock_data
        
    except ConnectionError as e:
        if ECOMMERCE_MOCK:
            ids = [int(id.strip()) for id in product_ids.split(',') if id.strip().isdigit()]
            return [{"id": id, "qty_available": 10.0} for id in ids]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Could not connect to the e-commerce service: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )
