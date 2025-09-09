"""
Inventory update utilities for Odoo integration
This module handles inventory adjustments after successful payments.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from ..services.odoo_service import execute_odoo_kw, get_product_by_id
from ..core.config import settings

logger = logging.getLogger(__name__)

async def adjust_inventory_after_purchase(product_id: int, purchased_quantity: float) -> bool:
    """
    DEPRECATED: Direct stock.quant manipulation - fragile and error-prone.
    Use update_inventory_via_delivery instead.
    """
    try:
        logger.info(f"Starting inventory adjustment for product {product_id}, quantity: {purchased_quantity}")
        
        # Get current product info
        product = await get_product_by_id(product_id)
        if not product:
            logger.error(f"Product {product_id} not found")
            return False
            
        current_qty = product.get('qty_available', 0)
        new_qty = current_qty - purchased_quantity
        
        if new_qty < 0:
            logger.error(f"Insufficient stock for product {product_id}. Current: {current_qty}, Purchased: {purchased_quantity}")
            return False
            
        logger.info(f"Product {product_id}: current={current_qty}, purchased={purchased_quantity}, new={new_qty}")
        
        # Find stock quant record
        quant_domain = [('product_id', '=', product_id), ('location_id', '=', 8)]
        logger.info(f"Searching for stock quant with domain: {quant_domain}")
        
        quant_ids = execute_odoo_kw('stock.quant', 'search', [quant_domain])
        if not quant_ids:
            logger.error(f"No stock quant found for product {product_id}")
            return False
            
        quant_id = quant_ids[0]
        
        # Update inventory quantity
        update_values = {'inventory_quantity': new_qty}
        logger.info(f"Updating existing quant {quant_id} with values: {update_values}")
        
        execute_odoo_kw('stock.quant', 'write', [[quant_id], update_values])
        
        # Apply inventory adjustment
        logger.info(f"Applying inventory adjustment for quant {quant_id}")
        execute_odoo_kw('stock.quant', 'action_apply_inventory', [[quant_id]])
        
        logger.info(f"Successfully updated inventory for product {product_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to adjust inventory for product {product_id}: {e}")
        logger.error(f"Full error details for product {product_id}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def update_inventory_via_delivery(
    session_id: str, 
    warehouse_code: str = "WH_BG",
    line_items: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    PROPER APPROACH: Create and validate Odoo delivery picking for inventory updates.
    This follows Odoo's standard stock operations workflow.
    """
    try:
        logger.info(f"Starting delivery-based inventory update for session {session_id}")
        
        # If no line_items provided, try to get from session metadata
        if not line_items:
            # This would be called from webhook with session data
            logger.warning("No line_items provided, cannot proceed")
            return {"status": "error", "message": "No line items provided"}
        
        # Build items with Odoo product IDs
        odoo_items: List[Tuple[int, float]] = []
        
        for item in line_items:
            qty = item.get("quantity", 1)
            product_id = item.get("odoo_product_id")
            
            if not product_id:
                logger.warning(f"No Odoo product ID found in line item: {item}")
                continue
                
            odoo_items.append((int(product_id), float(qty)))
        
        if not odoo_items:
            logger.error("No valid Odoo items found")
            return {"status": "error", "message": "No valid Odoo items found"}
        
        # Find outgoing picking type for the target warehouse
        wh_ids = execute_odoo_kw("stock.warehouse", "search", [[("code", "=", warehouse_code)]], {"limit": 1})
        if not wh_ids:
            raise ValueError(f"Warehouse with code '{warehouse_code}' not found in Odoo.")
        
        warehouse_id = wh_ids[0]
        picking_type_ids = execute_odoo_kw(
            "stock.picking.type", "search", 
            [[("warehouse_id", "=", warehouse_id), ("code", "=", "outgoing")]], 
            {"limit": 1}
        )
        
        if not picking_type_ids:
            raise ValueError("Outgoing picking type not found for warehouse.")
        
        picking_type_id = picking_type_ids[0]
        picking_type = execute_odoo_kw(
            "stock.picking.type", "read", 
            [[picking_type_id], ["default_location_src_id", "default_location_dest_id"]]
        )[0]
        
        src_loc = picking_type["default_location_src_id"][0]
        dest_loc = picking_type["default_location_dest_id"][0]
        
        # Create picking (delivery order)
        picking_vals = {
            "picking_type_id": picking_type_id,
            "location_id": src_loc,
            "location_dest_id": dest_loc,
            "origin": f"Stripe {session_id}",
        }
        
        picking_id = execute_odoo_kw("stock.picking", "create", [picking_vals])
        
        # Add stock moves for each product
        for prod_id, qty in odoo_items:
            prod = execute_odoo_kw("product.product", "read", [[prod_id], ["uom_id", "display_name"]])[0]
            move_vals = {
                "name": prod.get("display_name") or "Delivery",
                "product_id": prod_id,
                "product_uom": prod["uom_id"][0],
                "product_uom_qty": qty,
                "picking_id": picking_id,
                "location_id": src_loc,
                "location_dest_id": dest_loc,
            }
            execute_odoo_kw("stock.move", "create", [move_vals])
        
        # Confirm and assign
        execute_odoo_kw("stock.picking", "action_confirm", [[picking_id]])
        execute_odoo_kw("stock.picking", "action_assign", [[picking_id]])
        
        # Set qty_done = requested qty and validate
        mlines = execute_odoo_kw(
            "stock.move.line", "search_read", 
            [[("picking_id", "=", picking_id)]], 
            {"fields": ["id", "product_uom_qty", "qty_done"]}
        )
        
        for ml in mlines:
            execute_odoo_kw(
                "stock.move.line", "write", 
                [[ml["id"]], {"qty_done": ml["product_uom_qty"]}]
            )
        
        # Validate; handle wizards (immediate transfer/backorder)
        ctx = {
            "active_model": "stock.picking",
            "active_ids": [picking_id],
            "active_id": picking_id,
            "skip_backorder_confirmation": True,
            "default_immediate_transfer": True,
        }
        
        res = execute_odoo_kw("stock.picking", "button_validate", [[picking_id]], {"context": ctx})
        
        # Handle immediate transfer wizard
        if isinstance(res, dict) and res.get("res_model") == "stock.immediate.transfer":
            wiz_id = execute_odoo_kw("stock.immediate.transfer", "create", [{"pick_ids": [(4, picking_id)]}])
            execute_odoo_kw("stock.immediate.transfer", "process", [[wiz_id]])
        
        # Handle backorder wizard
        if isinstance(res, dict) and res.get("res_model") == "stock.backorder.confirmation":
            wiz_id = execute_odoo_kw("stock.backorder.confirmation", "create", [{"pick_ids": [(4, picking_id)]}])
            execute_odoo_kw("stock.backorder.confirmation", "process", [[wiz_id]])
        
        logger.info(f"Created and validated delivery picking {picking_id} for session {session_id}")
        return {
            "status": "ok", 
            "picking_id": picking_id, 
            "items": odoo_items,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Failed to update inventory via delivery for session {session_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e), "session_id": session_id}
