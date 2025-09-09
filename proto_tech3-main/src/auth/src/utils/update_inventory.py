# /src/ecommerce/service.py
# ... (all existing imports and functions) ...
from src.auth.logging import logger
from src.auth.src.ecommerce.service import execute_odoo_kw , get_product_by_id
# --- NEW: Function to adjust inventory after a purchase ---

async def adjust_inventory_after_purchase(product_id: int, purchased_quantity: float) -> bool:
    """
    Adjusts the inventory for a product after a sale.

    It fetches the current quantity, calculates the new quantity, and then
    updates the stock level in Odoo via an inventory adjustment.

    Args:
        product_id (int): The Odoo ID of the product sold.
        purchased_quantity (float): The quantity that was purchased.

    Returns:
        bool: True if the inventory was successfully updated, False otherwise.
    """
    if purchased_quantity <= 0:
        logger.warning(f"Attempted to adjust inventory with a non-positive quantity: {purchased_quantity}. Aborting.")
        return False

    logger.info(f"Starting inventory adjustment for product_id={product_id}. Purchased quantity: {purchased_quantity}")

    # Standard Stock Location ID (verify this in your Odoo instance)
    stock_location_id = 8

    try:
        # Step 1: Get the current available quantity for the product.
        # We need this to calculate the new stock level.
        product_data = await get_product_by_id(product_id)
        if not product_data:
            logger.error(f"Cannot adjust inventory: Product with ID {product_id} not found.")
            return False
            
        current_quantity = product_data.get('qty_available', 0.0)
        logger.info(f"Current on-hand quantity for product {product_id} is {current_quantity}.")

        # Step 2: Calculate the new quantity.
        new_quantity = current_quantity - purchased_quantity
        if new_quantity < 0:
            # This is an important business logic check.
            # You might want to allow backorders, but for now, we'll log an error.
            logger.error(
                f"Inventory adjustment for product {product_id} would result in negative stock "
                f"({new_quantity}). Aborting update. Current: {current_quantity}, Purchased: {purchased_quantity}"
            )
            return False

        logger.info(f"Calculated new quantity for product {product_id} will be {new_quantity}.")

        # Step 3: Find the specific stock quant for the product in the target location.
        domain = [
            ('product_id', '=', product_id),
            ('location_id', '=', stock_location_id)
        ]
        quant_ids = execute_odoo_kw('stock.quant', 'search', [domain], {'limit': 1})

        # Step 4: Create or write to the stock quant using the 'inventory_quantity' field.
        if not quant_ids:
            # This case is rare for a product being sold, as it implies it had 0 stock.
            logger.warning(f"No existing stock.quant for product {product_id}. Creating a new one.")
            create_values = {
                'product_id': product_id,
                'location_id': stock_location_id,
                'inventory_quantity': new_quantity, # Use the correct field name
            }
            execute_odoo_kw('stock.quant', 'create', [create_values])
            execute_odoo_kw('stock.quant', 'action_apply_inventory', [[quant_id]])

        else:
            # This is the most common case: update the existing stock record.
            quant_id = quant_ids[0]
            update_values = {'inventory_quantity': new_quantity} # Use the correct field name
            
            execute_odoo_kw('stock.quant', 'write', [[quant_id], update_values])
            execute_odoo_kw('stock.quant', 'action_apply_inventory', [[quant_id]])

            logger.info("updated quantity successfully>>>>>>>>>>>>>>>>>")

        logger.info(f"Successfully submitted inventory adjustment for product_id={product_id}. New target quantity is {new_quantity}.")
        return True

    except Exception:
        logger.exception(f"An unexpected error occurred during inventory adjustment for product_id={product_id}.")
        return False
    

