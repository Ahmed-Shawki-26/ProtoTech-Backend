# odoo_service.py
import os
import logging
from typing import List, Dict, Any
from functools import lru_cache
import xmlrpc.client

logger = logging.getLogger(__name__)

# Odoo configuration
ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")

@lru_cache(maxsize=1)
def get_odoo_client():
    """Get Odoo client connection."""
    try:
        # Create XML-RPC client
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        
        # Authenticate
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
        if not uid:
            raise ConnectionError("Failed to authenticate with Odoo")
            
        return uid, models
    except Exception as e:
        logger.error(f"Could not connect to or authenticate with Odoo: {e}")
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
        logger.error(f"Odoo API Error: {e}")
        raise ValueError(f"Odoo API Error: {e}")

async def get_product_by_id(product_id: int) -> Dict | None:
    """Fetches a single product by its Odoo ID."""
    logger.info(f"Fetching product by ID: {product_id}")
    domain = [['id', '=', product_id]]
    fields = [
        'id', 'name', 'description_sale', 'qty_available', 'list_price', 
        'standard_price', 'default_code', 'barcode', 'categ_id', 'uom_id',
        'type', 'image_1920'
    ]
    args = [domain]
    kwargs = {'fields': fields, 'limit': 1}
    products = execute_odoo_kw('product.product', 'search_read', args, kwargs)
    return products[0] if products else None

async def get_all_products(limit: int = 20, offset: int = 0) -> List[Dict]:
    """Fetches a paginated list of products from Odoo."""
    logger.info(f"Fetching products from Odoo: limit={limit}, offset={offset}")
    domain = [['type', '=', 'consu']]
    fields = ['id', 'name', 'qty_available', 'list_price', 'default_code', 'categ_id', 'image_1920']
    args = [domain]
    kwargs = {'fields': fields, 'limit': limit, 'offset': offset}
    return execute_odoo_kw('product.product', 'search_read', args, kwargs)

async def get_all_categories() -> List[Dict]:
    """Fetches all product categories from Odoo."""
    logger.info("Fetching categories from Odoo")
    domain = []
    fields = ['id', 'name', 'display_name', 'parent_id']
    args = [domain]
    kwargs = {'fields': fields}
    return execute_odoo_kw('product.category', 'search_read', args, kwargs)

def process_product_data(p_in: dict) -> dict:
    """Process raw Odoo product data into frontend-friendly format."""
    # Generate proper image URL instead of base64 data URL
    image_url = None
    if p_in.get("image_1920"):
        # Create a proper URL endpoint for serving images
        # This should point to an endpoint that serves images from Odoo
        image_url = f"/api/v1/ecommerce/product-image/{p_in.get('id')}"
    
    return {
        "id": p_in.get("id"),
        "name": p_in.get("name", ""),
        "description": p_in.get("description_sale", ""),
        "price": p_in.get("list_price", 0.0),
        "stock": p_in.get("qty_available", 0.0),
        "sku": p_in.get("default_code", ""),
        "barcode": p_in.get("barcode", ""),
        "category_id": p_in.get("categ_id", [None, ""])[0] if p_in.get("categ_id") else None,
        "category_name": p_in.get("categ_id", [None, ""])[1] if p_in.get("categ_id") else "",
        "image_url": image_url,
        "unit_of_measure": p_in.get("uom_id", [None, ""])[1] if p_in.get("uom_id") else "",
        "cost_price": p_in.get("standard_price", 0.0),
        "product_type": p_in.get("type", "consu")
    }
