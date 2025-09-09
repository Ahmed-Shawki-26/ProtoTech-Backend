# /src/ecommerce/controller.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from starlette import status
from dotenv import load_dotenv 
load_dotenv()
# FIX: Get a module-specific logger
from src.auth.src.logging import logger
from src.auth.src.auth import service, models


router = APIRouter(
    prefix="/ecommerce",
    tags=["E-commerce"]
)

def process_product_data(p_in: dict) -> dict:
    # ... (This helper function is fine, but we'll add a log inside the endpoints) ...
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
    if p_in.get('image_1920'):
        p_out['image_url'] = f"data:image/jpeg;base64,{p_in['image_1920']}"
    else:
        p_out['image_url'] = None
    if p_in.get('categ_id'):
        p_out['categ_id'] = models.OdooReference.from_odoo(p_in['categ_id'])
    else:
        p_out['categ_id'] = None
    if p_in.get('uom_id'):
        p_out['uom_id'] = models.OdooReference.from_odoo(p_in['uom_id'])
    else:
        p_out['uom_id'] = None
    return p_out


@router.get("/products")
async def get_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get a paginated list of all available products."""
    logger.info(f"Received request for /products with limit={limit}, offset={offset}")
    try:
        products_raw = await service.get_all_products(limit=limit, offset=offset)
        logger.info(f"Successfully fetched {len(products_raw)} products from Odoo service.")
        
        processed_products = [process_product_data(p) for p in products_raw]
        return processed_products
    except ConnectionError as e:
        logger.error(f"Could not connect to Odoo for /products request: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the e-commerce service.")
    except Exception:
        # FIX: Use logger.exception to get the full traceback
        logger.exception("An unexpected error occurred while fetching and processing products.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")


@router.get("/products/{product_id}")
async def get_product_detail(product_id: int):
    """Get the full details for a single product by its ID."""
    logger.info(f"Received request for /products/{product_id}")
    try:
        product_raw = await service.get_product_by_id(product_id)
        if not product_raw:
            logger.warning(f"Product with ID {product_id} not found in Odoo.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        
        logger.info(f"Successfully fetched product {product_id} from Odoo service.")
        return process_product_data(product_raw)
    except ConnectionError as e:
        logger.error(f"Could not connect to Odoo for /products/{product_id} request: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the e-commerce service.")
    except Exception:
        # FIX: Use logger.exception to get the full traceback
        logger.exception(f"An unexpected error occurred while fetching product {product_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")


@router.get("/categories")
async def get_categories():
    """Get a list of all product categories."""
    logger.info("Received request for /categories")
    try:
        categories_raw = await service.get_all_categories()
        logger.info(f"Successfully fetched {len(categories_raw)} categories from Odoo service.")
        for cat in categories_raw:
            if cat.get('parent_id'):
                cat['parent_id'] = models.OdooReference.from_odoo(cat['parent_id'])
        return categories_raw
    except ConnectionError as e:
        logger.error(f"Could not connect to Odoo for /categories request: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not connect to the e-commerce service.")
    except Exception:
        # FIX: Use logger.exception to get the full traceback
        logger.exception("An unexpected error occurred while fetching categories.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")
    
