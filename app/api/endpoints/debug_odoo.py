# app/api/endpoints/debug_odoo.py

import os
import xmlrpc.client
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug/odoo", tags=["debug"])

@router.get("/ping")
def odoo_ping():
    """Test Odoo connectivity and authentication"""
    url = os.getenv("ODOO_URL")
    db = os.getenv("ODOO_DB")
    user = os.getenv("ODOO_USERNAME") or os.getenv("ODOO_EMAIL")
    pwd = os.getenv("ODOO_PASSWORD") or os.getenv("ODOO_API_KEY")
    
    # Check if all required env vars are present
    env_status = {
        "ODOO_URL": bool(url),
        "ODOO_DB": bool(db),
        "ODOO_USERNAME": bool(user),
        "ODOO_PASSWORD": bool(pwd)
    }
    
    if not all([url, db, user, pwd]):
        return {
            "ok": False, 
            "reason": "missing_env", 
            "present": env_status,
            "message": "Missing required Odoo environment variables"
        }
    
    try:
        # Test connection to Odoo
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate(db, user, pwd, {})
        
        if not uid:
            return {
                "ok": False, 
                "reason": "auth_failed",
                "env_status": env_status,
                "message": "Odoo authentication failed - check credentials"
            }
        
        return {
            "ok": True, 
            "uid": uid,
            "env_status": env_status,
            "message": "Odoo connection successful"
        }
    except Exception as e:
        return {
            "ok": False, 
            "reason": "connection_error",
            "env_status": env_status,
            "error": str(e),
            "message": f"Failed to connect to Odoo: {e}"
        }

@router.get("/products")
def odoo_products(limit: int = 5):
    """Test fetching products directly from Odoo"""
    url = os.getenv("ODOO_URL")
    db = os.getenv("ODOO_DB")
    user = os.getenv("ODOO_USERNAME") or os.getenv("ODOO_EMAIL")
    pwd = os.getenv("ODOO_PASSWORD") or os.getenv("ODOO_API_KEY")
    
    if not all([url, db, user, pwd]):
        raise HTTPException(500, "Missing Odoo environment variables")
    
    try:
        # Connect to Odoo
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        uid = common.authenticate(db, user, pwd, {})
        
        if not uid:
            raise HTTPException(500, "Odoo authentication failed")
        
        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        
        # Search for products with typical e-commerce filters
        domain = [
            ["type", "=", "consu"],  # Consumer products
            ["website_published", "=", True]  # Published on website
        ]
        fields = ["id", "name", "list_price", "image_1920", "qty_available", "default_code"]
        
        # First, search for product IDs
        ids = models.execute_kw(
            db, uid, pwd, 
            "product.template", 
            "search", 
            [domain], 
            {"limit": limit}
        )
        
        if not ids:
            return {
                "count": 0, 
                "items": [],
                "message": "No products found matching criteria",
                "domain": domain
            }
        
        # Then read the product details
        products = models.execute_kw(
            db, uid, pwd, 
            "product.template", 
            "read", 
            [ids], 
            {"fields": fields}
        )
        
        return {
            "count": len(products), 
            "items": products,
            "domain": domain,
            "message": f"Successfully fetched {len(products)} products from Odoo"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Odoo products fetch failed: {e}")

@router.get("/config")
def odoo_config():
    """Show current Odoo configuration (without sensitive data)"""
    url = os.getenv("ODOO_URL")
    db = os.getenv("ODOO_DB")
    user = os.getenv("ODOO_USERNAME") or os.getenv("ODOO_EMAIL")
    pwd = os.getenv("ODOO_PASSWORD") or os.getenv("ODOO_API_KEY")
    
    return {
        "ODOO_URL": url,
        "ODOO_DB": db,
        "ODOO_USERNAME": user,
        "ODOO_PASSWORD": "***" if pwd else None,
        "ECOMMERCE_MOCK": os.getenv("ECOMMERCE_MOCK", "0"),
        "all_env_present": all([url, db, user, pwd])
    }

@router.get("/test-connection")
def test_connection():
    """Comprehensive Odoo connection test"""
    try:
        # Test ping first
        ping_result = odoo_ping()
        
        if not ping_result["ok"]:
            return ping_result
        
        # Test products fetch
        products_result = odoo_products(limit=3)
        
        return {
            "connection": ping_result,
            "products": products_result,
            "overall_status": "SUCCESS" if ping_result["ok"] else "FAILED"
        }
        
    except Exception as e:
        return {
            "overall_status": "ERROR",
            "error": str(e),
            "message": "Connection test failed"
        }

@router.get("/routes")
def list_routes():
    """List all registered routes for debugging"""
    from fastapi import FastAPI
    from ...api.main import api_router
    
    routes = []
    for route in api_router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'Unknown')
            })
    
    return {
        "total_routes": len(routes),
        "routes": routes,
        "ecommerce_routes": [r for r in routes if '/ecommerce' in r['path']],
        "debug_routes": [r for r in routes if '/debug' in r['path']]
    }
