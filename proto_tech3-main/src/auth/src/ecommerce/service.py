# /src/ecommerce/service.py
import xmlrpc.client
import os
from functools import lru_cache
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()
# FIX: Get a module-specific logger
from src.auth.src.logging import logger

# --- Odoo Configuration (remains the same) ---
ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME") # Renamed for clarity from ODOO_MAIL
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD") # Renamed for clarity from ODOO_API_KEY

if not all([ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD]):
    raise ValueError("Missing Odoo configuration. Please check your .env file.")

@lru_cache(maxsize=1)
def get_odoo_client():
    """Connects to Odoo and authenticates, returning the UID and models proxy."""
    try:
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        if not uid:
            # This is a specific, known failure state.
            logger.error("Odoo authentication failed. UID is empty. Check credentials in .env file.")
            raise ConnectionError("Odoo authentication failed. Check credentials.")
        logger.info("Successfully connected and authenticated with Odoo.")
        return uid, models
    except Exception:
        # FIX: Use logger.exception to get the full traceback for any connection error
        logger.exception("An unhandled exception occurred while connecting to Odoo.")
        raise ConnectionError(f"Could not connect to or authenticate with Odoo at {ODOO_URL}")

def execute_odoo_kw(model_name: str, method: str, args: List = None, kwargs: Dict = None) -> Any:
    """
    A generic wrapper to execute a keyword method on an Odoo model.
    Handles connection, authentication, and specific non-critical errors.
    """
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
        
    try:
        uid, models = get_odoo_client()
        
        logger.debug(f"Executing Odoo RPC: model={model_name}, method={method}, args={args}, kwargs={kwargs}")
        
        result = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            model_name, method,
            args,
            kwargs
        )
        return result

    except xmlrpc.client.Fault as e:
        # --- THIS IS THE FIX ---
        # We specifically check for the known "successful failure" error from Odoo.
        # If an operation succeeds but returns None, Odoo's RPC layer fails to serialize it.
        # We can safely treat this specific error as a success for 'write' or 'create' operations.
        if "cannot marshal None" in e.faultString:
            logger.warning(
                f"Odoo RPC for {model_name}.{method} returned a 'cannot marshal None' fault. "
                f"This is being treated as a SUCCESS because the operation likely completed."
            )
            return True  # Return a success-like value
        else:
            # This is a real, unexpected error from Odoo.
            logger.error(
                f"Odoo API returned a critical error for model '{model_name}' and method '{method}'. "
                f"Fault code: {e.faultCode}, Fault string: {e.faultString}"
            )
            raise ValueError(f"Odoo API Error: {e.faultString}")
    except Exception:
        logger.exception(f"An unexpected Python-level error occurred during Odoo RPC call for model '{model_name}'")
        raise

# FIX: Standardized the structure and corrected the domain format for all functions
async def get_all_products(limit: int = 20, offset: int = 0) -> List[Dict]:
    """Fetches a paginated list of products from Odoo."""
    logger.info(f"Fetching products from Odoo: limit={limit}, offset={offset}")
    domain = [['type', '=', 'consu']]
    fields = ['id', 'name', 'qty_available', 'list_price', 'default_code', 'categ_id', 'image_1920']
    args = [domain]
    kwargs = {'fields': fields, 'limit': limit, 'offset': offset}
    return execute_odoo_kw('product.product', 'search_read', args, kwargs)

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

async def get_all_categories() -> List[Dict]:
    """Fetches all product categories from Odoo."""
    logger.info("Fetching all product categories.")
    fields = ['id', 'name', 'parent_id', 'product_count']
    args = [[]]
    kwargs = {'fields': fields}
    return execute_odoo_kw('product.category', 'search_read', args, kwargs)