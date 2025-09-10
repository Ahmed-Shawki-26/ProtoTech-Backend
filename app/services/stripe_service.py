import stripe
import logging
import os
from typing import Dict, Any, Optional, List, Tuple
from fastapi import HTTPException, status
from ..schemas.checkout import CheckoutRequest, PaymentConfirmation
from ..email_service import send_payment_confirmation_email
from ..services.odoo_service import get_product_by_id, execute_odoo_kw

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Default URLs - using shortest possible URLs to avoid length issues
DEFAULT_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://proto-tech-frontend.vercel.app/confirmation")
DEFAULT_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://proto-tech-frontend.vercel.app/cart")
DEFAULT_CURRENCY = os.getenv("STRIPE_CURRENCY", "egp")  # Changed from "usd" to "egp"
MINIMUM_CHARGE_EGP = float(os.getenv("MINIMUM_CHARGE_EGP", "25"))

async def create_checkout_session(data: CheckoutRequest) -> Dict[str, Any]:
    """
    Create a Stripe checkout session for payment processing.
    - Validates each item against Odoo (price and available stock) for e-commerce products
    - Handles custom manufacturing orders (PCB, 3D printing) without Odoo validation
    - Uses Odoo price to build Stripe line items for e-commerce products
    - Stores compact cart metadata (ids and quantities) for webhook processing
    - Includes comprehensive cart validation and limits
    """
    try:
        logger.info(f"Creating checkout session for customer {data.customer_id}")

        import json
        
        # Cart validation constants
        MAX_QUANTITY_PER_ITEM = 100
        MAX_CART_TOTAL = 100000  # EGP
        MAX_ITEMS_IN_CART = 50
        
        # Validate cart limits
        if len(data.items) > MAX_ITEMS_IN_CART:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cart cannot contain more than {MAX_ITEMS_IN_CART} different items."
            )
        
        total_quantity = sum(int(item.get("quantity", 1)) for item in data.items)
        if total_quantity > MAX_QUANTITY_PER_ITEM * MAX_ITEMS_IN_CART:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Total quantity cannot exceed {MAX_QUANTITY_PER_ITEM * MAX_ITEMS_IN_CART} items."
            )
        
        # Validate items and build Stripe line items
        line_items: list[dict[str, Any]] = []
        validated_items_for_metadata: list[dict[str, Any]] = []
        total_cart_value = 0.0

        for item in data.items:
            product_id = item.get("id")
            quantity = int(item.get("quantity", 1))
            product_name = item.get("name", "Product")
            price_from_request = float(item.get("price", 0.0))
            
            if not product_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each cart item must include an 'id' field."
                )
            if quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid quantity for product {product_id}."
                )
            if quantity > MAX_QUANTITY_PER_ITEM:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Maximum quantity allowed is {MAX_QUANTITY_PER_ITEM} for {product_name}."
                )
            if price_from_request <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product '{product_name}' has no purchasable price."
                )

            # Check if this is an Odoo product ID (numeric) or custom manufacturing order
            try:
                odoo_product_id = int(product_id)
                # This is an Odoo product - validate against Odoo
                product = await get_product_by_id(odoo_product_id)
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product with ID {product_id} not found in Odoo."
                    )

                product_name = product.get("name", "Product")
                price_from_odoo = float(product.get("list_price", 0.0))
                # Prefer the most optimistic reliable stock indicator to avoid false negatives
                stock_available = float(
                    product.get("qty_available")
                    or product.get("virtual_available")
                    or product.get("free_qty")
                    or 0.0
                )

                if price_from_odoo <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product '{product_name}' has no purchasable price in Odoo."
                    )
                
                # More lenient stock validation - allow small discrepancies
                # Check if stock is completely out or significantly insufficient
                if stock_available <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product '{product_name}' is out of stock."
                    )
                elif stock_available < quantity:
                    # Only reject if the difference is significant (more than 1 unit)
                    if quantity - stock_available > 1:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Insufficient stock for '{product_name}'. Requested {quantity}, available {stock_available}."
                        )
                    else:
                        # Log the small discrepancy but allow the purchase
                        logger.warning(f"Small stock discrepancy for product {product_name}: requested {quantity}, available {stock_available}")
                        # Use the available stock quantity instead of requested
                        quantity = int(stock_available)

                # Use Odoo price for e-commerce products
                unit_amount = int(price_from_odoo * 100)
                total_cart_value += price_from_odoo * quantity
                validated_items_for_metadata.append({"id": odoo_product_id, "quantity": quantity, "type": "odoo_product"})
                
            except ValueError:
                # This is a custom manufacturing order (PCB, 3D printing) - use provided price
                unit_amount = int(price_from_request * 100)
                total_cart_value += price_from_request * quantity
                validated_items_for_metadata.append({"id": product_id, "quantity": quantity, "type": "custom_order"})

            line_items.append({
                "price_data": {
                    "currency": data.currency or DEFAULT_CURRENCY,
                    "product_data": {
                        "name": product_name[:100],
                    },
                    "unit_amount": unit_amount,
                },
                "quantity": quantity,
            })

        # Enforce minimum and maximum cart value in EGP
        if total_cart_value < MINIMUM_CHARGE_EGP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum charge is {MINIMUM_CHARGE_EGP:.0f} EGP. Please add more items to your cart."
            )
        if total_cart_value > MAX_CART_TOTAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cart total cannot exceed {MAX_CART_TOTAL} EGP."
            )

        if not line_items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty.")

        # Create checkout session using validated line items and compact metadata
        session = stripe.checkout.Session.create(
            line_items=line_items,
            metadata={
                "user_id": data.customer_id,
                "items": json.dumps(validated_items_for_metadata),
                "customer_phone": data.customer_phone or "",
            },
            mode="payment",
            success_url=f"{data.success_url or DEFAULT_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=data.cancel_url or DEFAULT_CANCEL_URL,
            payment_method_types=["card"],
            customer_email=data.customer_email,
        )

        logger.info(f"Checkout session created successfully: {session.id}")

        return {
            "url": session.url,
            "session_id": session.id,
            "success": True,
            "message": "Checkout session created successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )

async def handle_webhook_event(event: Dict[str, Any]) -> Optional[PaymentConfirmation]:
    """
    Handle Stripe webhook events, particularly payment confirmations
    """
    try:
        event_type = event.get("type")
        logger.info(f"Processing webhook event: {event_type}")

        if event_type == "checkout.session.completed":
            return await _handle_checkout_completed(event)
        elif event_type == "payment_intent.succeeded":
            return _handle_payment_succeeded(event)
        elif event_type == "payment_intent.payment_failed":
            return _handle_payment_failed(event)
        else:
            logger.info(f"Unhandled event type: {event_type}")
            return None

    except Exception as e:
        logger.error(f"Error handling webhook event: {e}")
        raise

async def _handle_checkout_completed(event: Dict[str, Any]) -> PaymentConfirmation:
    """Handle checkout.session.completed event"""
    session = event["data"]["object"]
    
    # Extract payment details
    payment_intent_id = session.get("payment_intent")
    amount = session.get("amount_total", 0)
    currency = session.get("currency", "egp")  # Default to EGP
    customer_email = session.get("customer_details", {}).get("email", "")
    customer_name = session.get("customer_details", {}).get("name", "")
    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id", "")
    
    # Create order ID from session ID
    order_id = f"order_{session['id']}"
    
    logger.info(f"Payment completed: user_id={user_id}, email={customer_email}, amount={amount} {currency}")
    logger.info(f"Session metadata: {metadata}")
    
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
        
        # Update inventory in Odoo via proper stock pickings
        logger.info("Starting inventory update via stock pickings...")
        try:
            await update_odoo_via_delivery_from_session(session['id'], warehouse_code="WH_BG")
            inventory_updated = True
            logger.info("Inventory update via stock pickings completed successfully")
        except Exception as e:
            logger.error(f"Failed to update inventory via stock pickings: {e}")
            logger.exception("Inventory update error details:")
            # Don't fail the entire webhook for inventory issues
            inventory_updated = False
        
        # Clear user's cart after successful payment
        logger.info(f"Starting cart clearing for user {user_id}...")
        await _clear_user_cart(user_id)
        cart_cleared = True
        logger.info(f"Cart cleared for user {user_id} after successful payment")
        
        # Send confirmation email
        try:
            await send_payment_confirmation_email(
                recipient_email=customer_email,
                order_data={
                    "customer_name": customer_name or "Customer",
                    "order_id": order_id,
                    "amount": f"{amount/100:.2f} {currency.upper()}",
                    "currency": currency.upper(),
                    "payment_intent_id": payment_intent_id
                }
            )
            logger.info(f"Confirmation email sent to {customer_email}")
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {e}")
            # Email failure shouldn't affect the order
        
        return PaymentConfirmation(
            order_id=order_id,
            payment_intent_id=payment_intent_id,
            amount=amount,
            currency=currency,
            status="completed",
            customer_email=customer_email,
            customer_name=customer_name,
            created_at=session.get("created", 0)
        )
        
    except Exception as e:
        logger.error(f"Error processing checkout completion: {e}")
        logger.exception("Checkout completion error details:")
        
        # Rollback operations if needed
        await _rollback_payment_processing(session, user_id, order_created, inventory_updated, cart_cleared)
        
        # Re-raise the exception to ensure proper error handling
        raise

async def _update_inventory_after_purchase(metadata: Dict[str, Any]):
    """Update inventory in Odoo after successful purchase"""
    try:
        import json
        from ..services.odoo_service import execute_odoo_kw, get_product_by_id
        
        # Parse items from metadata
        items_json = metadata.get("items", "[]")
        items = json.loads(items_json)
        
        logger.info(f"Processing {len(items)} items after purchase")
        logger.info(f"Items data: {items}")
        
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        
        for item in items:
            product_id = item.get("id")
            quantity = item.get("quantity", 1)
            item_type = item.get("type", "odoo_product")  # Default to odoo_product for backward compatibility
            
            logger.info(f"Processing item: id={product_id}, quantity={quantity}, type={item_type}")
            
            if not product_id:
                logger.warning("Skipping item with missing product ID")
                failed_count += 1
                continue
            
            # Handle different item types
            if item_type == "custom_order":
                # Custom manufacturing orders (PCB, 3D printing) - no inventory update needed
                logger.info(f"Skipping inventory update for custom order: {product_id}")
                skipped_count += 1
                continue
            elif item_type == "odoo_product":
                # Odoo products - update inventory
                try:
                    # Convert to int for Odoo product ID
                    odoo_product_id = int(product_id)
                    
                    # Get current product data
                    logger.info(f"Fetching product data for Odoo product ID: {odoo_product_id}")
                    product_data = await get_product_by_id(odoo_product_id)
                    if not product_data:
                        logger.error(f"Product {product_id} not found in Odoo")
                        failed_count += 1
                        continue
                        
                    current_quantity = product_data.get('qty_available', 0.0)
                    new_quantity = current_quantity - quantity
                    
                    logger.info(f"Product {product_id}: current={current_quantity}, requested={quantity}, new={new_quantity}")
                    
                    if new_quantity < 0:
                        logger.error(f"Insufficient stock for product {product_id}. Current: {current_quantity}, Requested: {quantity}")
                        failed_count += 1
                        continue
                    
                    # Update stock quant
                    stock_location_id = 8  # Standard stock location
                    domain = [
                        ('product_id', '=', odoo_product_id),
                        ('location_id', '=', stock_location_id)
                    ]
                    
                    logger.info(f"Searching for stock quant with domain: {domain}")
                    quant_ids = execute_odoo_kw('stock.quant', 'search', [domain], {'limit': 1})
                    
                    if quant_ids:
                        quant_id = quant_ids[0]
                        update_values = {'inventory_quantity': new_quantity}
                        logger.info(f"Updating existing quant {quant_id} with values: {update_values}")
                        execute_odoo_kw('stock.quant', 'write', [[quant_id], update_values])
                        execute_odoo_kw('stock.quant', 'action_apply_inventory', [[quant_id]])
                        logger.info(f"Updated inventory for product {product_id}: {current_quantity} -> {new_quantity}")
                        updated_count += 1
                    else:
                        # Create new stock quant if it doesn't exist
                        create_values = {
                            'product_id': odoo_product_id,
                            'location_id': stock_location_id,
                            'inventory_quantity': new_quantity,
                        }
                        logger.info(f"Creating new stock quant with values: {create_values}")
                        quant_id = execute_odoo_kw('stock.quant', 'create', [create_values])
                        execute_odoo_kw('stock.quant', 'action_apply_inventory', [[quant_id]])
                        logger.info(f"Created new inventory record for product {product_id}: {new_quantity}")
                        updated_count += 1
                        
                except ValueError as e:
                    logger.error(f"Invalid Odoo product ID format: {product_id}, error: {e}")
                    failed_count += 1
                    continue
                except Exception as e:
                    logger.error(f"Failed to update inventory for product {product_id}: {e}")
                    logger.exception(f"Full error details for product {product_id}")
                    failed_count += 1
                    continue
            else:
                # Unknown item type - skip
                logger.warning(f"Unknown item type '{item_type}' for product {product_id}")
                skipped_count += 1
                continue
                
        logger.info(f"Inventory processing completed: {updated_count} updated, {failed_count} failed, {skipped_count} skipped")
        
        # If any items failed, log a warning
        if failed_count > 0:
            logger.warning(f"Inventory update had {failed_count} failures out of {len(items)} total items")
                
    except Exception as e:
        logger.error(f"Error processing inventory after purchase: {e}")
        logger.exception("Full inventory update error details:")
        raise

async def update_odoo_via_delivery_from_session(session_id: str, warehouse_code: str = "WH_BG") -> Dict[str, Any]:
    """
    Update Odoo inventory via proper stock pickings for storable products,
    or create sales orders for consumable products.
    This handles both product types appropriately.
    """
    try:
        import stripe
        import json
        from datetime import datetime
        
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        # 1) Get session with line items and products expanded
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["line_items.data.price.product"]
        )
        
        payment_intent_id = session.get("payment_intent") or session.get("id")
        idem_key = f"odoo_inv_{payment_intent_id}"
        
        # Check idempotency (simple in-memory check for now)
        if hasattr(update_odoo_via_delivery_from_session, '_processed_keys'):
            if idem_key in update_odoo_via_delivery_from_session._processed_keys:
                logger.info(f"[Idempotent] Already processed {idem_key}, skipping")
                return {"status": "skipped", "reason": "idempotent"}
        else:
            update_odoo_via_delivery_from_session._processed_keys = set()
        
        update_odoo_via_delivery_from_session._processed_keys.add(idem_key)
        
        logger.info(f"Processing session {session_id} for inventory update")
        
        # 2) Build items with Odoo product IDs and their types
        odoo_items: List[Dict[str, Any]] = []  # (product_id, quantity, type, name)
        
        # PRIMARY SOURCE: Use server-authored session metadata
        md_items_raw = (session.get("metadata") or {}).get("items")
        if md_items_raw:
            try:
                md_items = json.loads(md_items_raw)
                logger.info(f"Found {len(md_items)} items in session metadata")
                
                for it in md_items:
                    odoo_id = int(it["id"])
                    qty = int(it.get("quantity", 1))
                    if qty <= 0:
                        continue
                    
                    # Verify product exists and get its type
                    try:
                        p = execute_odoo_kw("product.product", "read", [[odoo_id], ["type", "name", "default_code"]])[0]
                        product_type = p.get("type", "product")
                        
                        item_data = {
                            "odoo_id": odoo_id,
                            "quantity": float(qty),
                            "type": product_type,
                            "name": p.get("name"),
                            "sku": p.get("default_code")
                        }
                        
                        if product_type == "consu":
                            logger.info(f"Product {odoo_id} ({p.get('name')}) is consumable - will create sales order")
                        elif product_type == "product":
                            logger.info(f"Product {odoo_id} ({p.get('name')}) is storable - will create delivery picking")
                        else:
                            logger.warning(f"Product {odoo_id} ({p.get('name')}) has unknown type '{product_type}'")
                        
                        odoo_items.append(item_data)
                        logger.info(f"Added item from metadata: Odoo product {odoo_id} ({p.get('name')}), quantity {qty}, type: {product_type}")
                    except Exception as e:
                        logger.error(f"Failed to verify product {odoo_id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Failed to parse session.metadata.items: {e}")
                logger.exception("Metadata parsing error details:")
        
        # FALLBACK: Map via Stripe product/price metadata or SKU if metadata.items failed
        if not odoo_items:
            logger.info("No items from metadata, falling back to Stripe product mapping")
            line_items = session["line_items"]["data"]
            if not line_items:
                raise ValueError("No line items on session; cannot update inventory.")
            
            for li in line_items:
                qty = li.get("quantity") or 1
                price = li.get("price") or {}
                product = price.get("product") or {}
                
                odoo_product_id = None
                
                # Try explicit odoo_product_id in product/price metadata
                meta = (product.get("metadata") or {}) or {}
                if meta.get("odoo_product_id"):
                    odoo_product_id = int(meta["odoo_product_id"])
                    logger.info(f"Mapped metadata odoo_product_id '{meta['odoo_product_id']}' to Odoo product ID {odoo_product_id}")
                
                # Try SKU via default_code
                if not odoo_product_id:
                    sku = meta.get("sku") or price.get("nickname")
                    if sku:
                        ids = execute_odoo_kw('product.product', 'search', [[('default_code', '=', sku)]], {'limit': 1})
                        if ids:
                            odoo_product_id = ids[0]
                            logger.info(f"Mapped SKU '{sku}' to Odoo product ID {odoo_product_id}")
                
                # Last resort: try by name
                if not odoo_product_id:
                    pname = product.get("name") or li.get("description")
                    if pname:
                        ids = execute_odoo_kw("product.product", "search", [[("name", "ilike", pname)]], {"limit": 1})
                        if ids:
                            odoo_product_id = ids[0]
                            logger.info(f"Mapped name '{pname}' to Odoo product ID {odoo_product_id}")
                
                if not odoo_product_id:
                    raise ValueError(f"Unable to map Stripe item to Odoo product: {product.get('id')}")
                
                # Get product details
                try:
                    p = execute_odoo_kw("product.product", "read", [[odoo_product_id], ["type", "name", "default_code"]])[0]
                    product_type = p.get("type", "product")
                    
                    item_data = {
                        "odoo_id": odoo_product_id,
                        "quantity": float(qty),
                        "type": product_type,
                        "name": p.get("name"),
                        "sku": p.get("default_code")
                    }
                    
                    odoo_items.append(item_data)
                    logger.info(f"Added item from Stripe mapping: Odoo product {odoo_product_id} ({p.get('name')}), quantity {qty}, type: {product_type}")
                except Exception as e:
                    logger.error(f"Failed to get product details for {odoo_product_id}: {e}")
                    continue
        
        # Optional sanity check vs line_items quantities
        try:
            li_total_qty = sum(int(r.get("quantity") or 0) for r in session["line_items"]["data"])
            md_total_qty = sum(int(i["quantity"]) for i in odoo_items)
            if li_total_qty != md_total_qty:
                logger.warning(f"Quantity mismatch: line_items={li_total_qty} vs mapped={md_total_qty} for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to perform quantity sanity check: {e}")
        
        if not odoo_items:
            raise ValueError("No valid items found for inventory update")
        
        logger.info(f"Processing {len(odoo_items)} items for session {session_id}")
        
        # 3) Separate items by type
        storable_items = [item for item in odoo_items if item["type"] == "product"]
        consumable_items = [item for item in odoo_items if item["type"] == "consu"]
        
        logger.info(f"Found {len(storable_items)} storable items and {len(consumable_items)} consumable items")
        
        # 3) Get partner from customer email
        email = (session.get("customer_details") or {}).get("email")
        partner_id = None
        if email:
            # Try to find existing partner by email
            partner_ids = execute_odoo_kw("res.partner", "search", [[("email", "=", email)]], {"limit": 1})
            if partner_ids:
                partner_id = partner_ids[0]
                logger.info(f"Found existing partner {partner_id} for email {email}")
            else:
                # Create new partner
                partner_vals = {
                    "name": (session.get("customer_details") or {}).get("name") or email,
                    "email": email,
                }
                partner_id = execute_odoo_kw("res.partner", "create", [partner_vals])
                logger.info(f"Created new partner {partner_id} for email {email}")
        
        results = {
            "storable_pickings": [],
            "consumable_orders": [],
            "session_id": session_id
        }
        
        # 4) Process storable items (create delivery pickings)
        if storable_items:
            logger.info(f"Processing {len(storable_items)} storable items with delivery pickings")
            
            # Find outgoing picking type for the target warehouse
            wh_ids = execute_odoo_kw("stock.warehouse", "search", [[("code", "=", warehouse_code)]], {"limit": 1})
            if not wh_ids:
                raise ValueError(f"Warehouse with code '{warehouse_code}' not found in Odoo.")
            
            warehouse_id = wh_ids[0]
            logger.info(f"Found warehouse {warehouse_id} with code '{warehouse_code}'")
            
            picking_type_ids = execute_odoo_kw(
                "stock.picking.type", "search",
                [[("warehouse_id", "=", warehouse_id), ("code", "=", "outgoing")]],
                {"limit": 1}
            )
            if not picking_type_ids:
                raise ValueError("Outgoing picking type not found for warehouse.")
            
            picking_type_id = picking_type_ids[0]
            picking_type = execute_odoo_kw("stock.picking.type", "read", [[picking_type_id], ["default_location_src_id", "default_location_dest_id", "name"]])[0]
            src_loc = picking_type["default_location_src_id"][0]
            dest_loc = picking_type["default_location_dest_id"][0]
            
            logger.info(f"Using picking type {picking_type_id} ({picking_type['name']}): src={src_loc}, dest={dest_loc}")
            
            # Create picking (delivery order)
            picking_vals = {
                "picking_type_id": picking_type_id,
                "location_id": src_loc,
                "location_dest_id": dest_loc,
                "origin": f"Stripe {session_id}",
            }
            if partner_id:
                picking_vals["partner_id"] = partner_id
            
            picking_id = execute_odoo_kw("stock.picking", "create", [picking_vals])
            logger.info(f"Created picking {picking_id} for session {session_id}")
            
            # Add stock moves
            for item in storable_items:
                prod_id = item["odoo_id"]
                qty = item["quantity"]
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
                move_id = execute_odoo_kw("stock.move", "create", [move_vals])
                logger.info(f"Created move {move_id} for product {prod_id}, quantity {qty}")
            
            # Confirm and assign
            execute_odoo_kw("stock.picking", "action_confirm", [[picking_id]])
            logger.info(f"Confirmed picking {picking_id}")
            
            execute_odoo_kw("stock.picking", "action_assign", [[picking_id]])
            logger.info(f"Assigned picking {picking_id}")
            
            # Set qty_done = requested qty and validate
            mlines = execute_odoo_kw("stock.move.line", "search_read", [[("picking_id", "=", picking_id)]], {"fields": ["id", "qty_done", "quantity"]})
            for ml in mlines:
                requested_qty = ml.get("quantity", 0)
                execute_odoo_kw("stock.move.line", "write", [[ml["id"]], {"qty_done": requested_qty}])
                logger.info(f"Set qty_done={requested_qty} for move line {ml['id']}")
            
            # Validate; handle wizards
            ctx = {
                "active_model": "stock.picking",
                "active_ids": [picking_id],
                "active_id": picking_id,
                "skip_backorder_confirmation": True,
                "default_immediate_transfer": True,
            }
            res = execute_odoo_kw("stock.picking", "button_validate", [[picking_id]], {"context": ctx})
            logger.info(f"Validation result for picking {picking_id}: {res}")
            
            # Handle immediate transfer wizard
            if isinstance(res, dict) and res.get("res_model") == "stock.immediate.transfer":
                logger.info(f"Handling immediate transfer wizard for picking {picking_id}")
                wiz_id = execute_odoo_kw("stock.immediate.transfer", "create", [{"pick_ids": [(4, picking_id)]}])
                execute_odoo_kw("stock.immediate.transfer", "process", [[wiz_id]])
                logger.info(f"Processed immediate transfer wizard {wiz_id}")
            
            # Handle backorder wizard
            if isinstance(res, dict) and res.get("res_model") == "stock.backorder.confirmation":
                logger.info(f"Handling backorder wizard for picking {picking_id}")
                wiz_id = execute_odoo_kw("stock.backorder.confirmation", "create", [{"pick_ids": [(4, picking_id)]}])
                execute_odoo_kw("stock.backorder.confirmation", "process", [[wiz_id]])
                logger.info(f"Processed backorder wizard {wiz_id}")
            
            logger.info(f"Successfully created and validated delivery picking {picking_id} for session {session_id}")
            results["storable_pickings"].append({"picking_id": picking_id, "items": storable_items})
        
        # 5) Process consumable items (create sales orders)
        if consumable_items:
            logger.info(f"Processing {len(consumable_items)} consumable items with sales orders")
            
            # Create sales order for consumable items
            if partner_id:
                # Create sales order
                order_vals = {
                    "partner_id": partner_id,
                    "origin": f"Stripe {session_id}",
                    "date_order": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                
                order_id = execute_odoo_kw("sale.order", "create", [order_vals])
                logger.info(f"Created sales order {order_id} for session {session_id}")
                
                # Add order lines
                for item in consumable_items:
                    prod_id = item["odoo_id"]
                    qty = item["quantity"]
                    prod = execute_odoo_kw("product.product", "read", [[prod_id], ["uom_id", "list_price", "display_name"]])[0]
                    
                    line_vals = {
                        "order_id": order_id,
                        "product_id": prod_id,
                        "product_uom_qty": qty,
                        "product_uom": prod["uom_id"][0],
                        "price_unit": prod.get("list_price", 0.0),
                        "name": prod.get("display_name") or item["name"],
                    }
                    
                    line_id = execute_odoo_kw("sale.order.line", "create", [line_vals])
                    logger.info(f"Created order line {line_id} for product {prod_id}, quantity {qty}")
                
                # Confirm the sales order
                execute_odoo_kw("sale.order", "action_confirm", [[order_id]])
                logger.info(f"Confirmed sales order {order_id}")
                
                results["consumable_orders"].append({"order_id": order_id, "items": consumable_items})
            else:
                logger.warning("No partner found, skipping sales order creation for consumable items")
        
        logger.info(f"Successfully processed session {session_id}: {len(results['storable_pickings'])} pickings, {len(results['consumable_orders'])} orders")
        return results
        
    except Exception as e:
        logger.error(f"Error in update_odoo_via_delivery_from_session: {e}")
        logger.exception("Full error details:")
        raise

async def _get_odoo_items_for_session(session_id: str) -> Dict[str, Any]:
    """
    Extract Odoo product IDs and quantities from Stripe session.
    Primary source: session.metadata.items (server-authored)
    Fallback: Stripe product/price metadata or SKU mapping
    """
    try:
        import stripe
        import json
        
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        # Get session with expanded line_items
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["line_items.data.price.product"]
        )
        
        items: List[Dict[str, Any]] = []
        
        # 1) Preferred: use server-authored session metadata
        md_items_raw = (session.get("metadata") or {}).get("items")
        if md_items_raw:
            try:
                md_items = json.loads(md_items_raw)
                logger.info(f"Found {len(md_items)} items in session metadata")
                
                for it in md_items:
                    odoo_id = int(it["id"])
                    qty = int(it.get("quantity", 1))
                    if qty <= 0:
                        continue
                    
                    # Verify product exists
                    try:
                        p = execute_odoo_kw("product.product", "read", [[odoo_id], ["type", "name", "default_code"]])[0]
                        items.append({
                            "odoo_product_id": odoo_id, 
                            "quantity": qty,
                            "product_name": p.get("name"),
                            "product_type": p.get("type"),
                            "sku": p.get("default_code")
                        })
                        logger.info(f"Mapped from metadata: Product {odoo_id} ({p.get('name')}), qty {qty}")
                    except Exception as e:
                        logger.error(f"Failed to verify product {odoo_id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Failed to parse session.metadata.items: {e}")
                logger.exception("Metadata parsing error details:")
        
        # 2) Fallback: map via Stripe product/price metadata or SKU
        if not items:
            logger.info("No items from metadata, falling back to Stripe product mapping")
            line_items = session["line_items"]["data"]
            
            for li in line_items:
                qty = int(li.get("quantity") or 1)
                price = li.get("price") or {}
                product = price.get("product") or {}
                
                odoo_id = None
                
                # Try explicit odoo_product_id in product/price metadata
                meta = (product.get("metadata") or {}) or {}
                if meta.get("odoo_product_id"):
                    odoo_id = int(meta["odoo_product_id"])
                    logger.info(f"Mapped metadata odoo_product_id '{meta['odoo_product_id']}' to Odoo product ID {odoo_id}")
                
                # Try SKU via default_code
                if not odoo_id:
                    sku = meta.get("sku") or price.get("nickname")
                    if sku:
                        ids = execute_odoo_kw('product.product', 'search', [[('default_code', '=', sku)]], {'limit': 1})
                        if ids:
                            odoo_id = ids[0]
                            logger.info(f"Mapped SKU '{sku}' to Odoo product ID {odoo_id}")
                
                # Last resort: try by name
                if not odoo_id:
                    pname = product.get("name") or li.get("description")
                    if pname:
                        ids = execute_odoo_kw("product.product", "search", [[("name", "ilike", pname)]], {"limit": 1})
                        if ids:
                            odoo_id = ids[0]
                            logger.info(f"Mapped name '{pname}' to Odoo product ID {odoo_id}")
                
                if not odoo_id:
                    raise ValueError(f"Cannot map Stripe item to Odoo product: {product.get('id')}")
                
                # Get product details
                try:
                    p = execute_odoo_kw("product.product", "read", [[odoo_id], ["type", "name", "default_code"]])[0]
                    items.append({
                        "odoo_product_id": odoo_id, 
                        "quantity": qty,
                        "product_name": p.get("name"),
                        "product_type": p.get("type"),
                        "sku": p.get("default_code")
                    })
                    logger.info(f"Mapped from Stripe: Product {odoo_id} ({p.get('name')}), qty {qty}")
                except Exception as e:
                    logger.error(f"Failed to get product details for {odoo_id}: {e}")
                    continue
        
        # Optional sanity check vs line_items quantities
        try:
            li_total_qty = sum(int(r.get("quantity") or 0) for r in session["line_items"]["data"])
            md_total_qty = sum(int(i["quantity"]) for i in items)
            if li_total_qty != md_total_qty:
                logger.warning(f"Quantity mismatch: line_items={li_total_qty} vs mapped={md_total_qty} for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to perform quantity sanity check: {e}")
        
        email = (session.get("customer_details") or {}).get("email")
        payment_intent = session.get("payment_intent") or session.get("id")
        
        return {
            "items": items, 
            "customer_email": email, 
            "payment_intent": payment_intent,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error in _get_odoo_items_for_session: {e}")
        logger.exception("Full error details:")
        raise

def _handle_payment_succeeded(event: Dict[str, Any]) -> PaymentConfirmation:
    """Handle payment_intent.succeeded event"""
    payment_intent = event["data"]["object"]
    
    return PaymentConfirmation(
        order_id=f"order_{payment_intent['id']}",
        payment_intent_id=payment_intent['id'],
        amount=payment_intent.get("amount", 0),
        currency=payment_intent.get("currency", "usd"),
        status="succeeded",
        customer_email=payment_intent.get("receipt_email", ""),
        customer_name=None,
        created_at=payment_intent.get("created", 0)
    )

def _handle_payment_failed(event: Dict[str, Any]) -> PaymentConfirmation:
    """Handle payment_intent.payment_failed event"""
    payment_intent = event["data"]["object"]
    
    logger.warning(f"Payment failed: {payment_intent['id']}")
    
    return PaymentConfirmation(
        order_id=f"order_{payment_intent['id']}",
        payment_intent_id=payment_intent['id'],
        amount=payment_intent.get("amount", 0),
        currency=payment_intent.get("currency", "usd"),
        status="failed",
        customer_email=payment_intent.get("receipt_email", ""),
        customer_name=None,
        created_at=payment_intent.get("created", 0)
    )

def verify_webhook_signature(payload: bytes, signature: str) -> Dict[str, Any]:
    """
    Verify the webhook signature to ensure it's from Stripe
    """
    try:
        event = stripe.Webhook.construct_event(payload, signature, endpoint_secret)
        return event
    except ValueError as e:
        logger.warning("Invalid payload received in webhook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except Exception as e:
        logger.warning("Invalid signature in webhook")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

async def _clear_user_cart(user_id: str):
    """Clear user's cart after successful payment"""
    try:
        from sqlalchemy.orm import Session
        from ..database.core import get_db
        from ..cart.service import CartService
        
        # Get database session
        db = next(get_db())
        
        # Clear the user's cart
        success = CartService.clear_user_cart(db, user_id)
        
        if success:
            logger.info(f"Successfully cleared cart for user {user_id}")
        else:
            logger.warning(f"Cart was already empty for user {user_id}")
            
    except Exception as e:
        logger.error(f"Error clearing cart for user {user_id}: {e}")
        raise

async def _create_order_from_session(session: Dict[str, Any], user_id: str):
    """Create order in database from Stripe session data"""
    try:
        from sqlalchemy.orm import Session
        from ..database.core import get_db
        from ..orders.service import OrderService
        from ..schemas.orders import CreateOrderRequest
        import json
        from datetime import datetime
        
        # Get database session
        db = next(get_db())
        
        # Extract session data
        metadata = session.get("metadata", {})
        items_json = metadata.get("items", "[]")
        items = json.loads(items_json)
        
        # Calculate total amount
        amount_total = session.get("amount_total", 0) / 100  # Convert from cents
        
        # Generate order number
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        order_number = f"PT-{timestamp}-{session['id'][-6:].upper()}"
        
        # Create order request
        order_data = CreateOrderRequest(
            items=items,
            total_amount=amount_total,
            shipping_address={
                "email": session.get("customer_details", {}).get("email", ""),
                "name": session.get("customer_details", {}).get("name", ""),
                "address": session.get("customer_details", {}).get("address", {}),
            },
            billing_address=None,  # Use shipping address as billing
            shipping_cost=0.0,
            tax_amount=0.0,
            discount_amount=0.0,
            notes=f"Order created from Stripe session {session['id']}",
            shipping_method="standard",
            order_number=order_number
        )
        
        # Create user object for order service
        user = {"id": user_id, "user_id": user_id}
        
        # Create order
        order = await OrderService.create_order(db, user, order_data)
        
        # Update order with Stripe information
        await OrderService.update_payment_status(
            db, 
            str(order.id), 
            "paid",
            stripe_session_id=session['id'],
            stripe_payment_intent_id=session.get("payment_intent")
        )
        
        logger.info(f"Order created successfully: {order.id} with number {order_number}")
        return order
        
    except Exception as e:
        logger.error(f"Failed to create order from session: {e}")
        raise

async def _rollback_payment_processing(session: Dict[str, Any], user_id: str, order_created: bool, inventory_updated: bool, cart_cleared: bool):
    """Rollback payment processing in case of failures"""
    logger.warning(f"Rolling back payment processing: order_created={order_created}, inventory_updated={inventory_updated}, cart_cleared={cart_cleared}")
    
    try:
        # Rollback order creation if it was created
        if order_created:
            try:
                from ..orders.service import OrderService
                from ..database.core import get_db
                db = next(get_db())
                
                # Find and cancel the order
                order = await OrderService.get_order_by_stripe_session(db, session['id'])
                if order:
                    await OrderService.update_payment_status(db, str(order.id), "failed")
                    logger.info(f"Rolled back order {order.id}")
            except Exception as e:
                logger.error(f"Failed to rollback order: {e}")
        
        # Rollback inventory updates if they were applied
        if inventory_updated:
            try:
                await _rollback_inventory_updates(session.get("metadata", {}))
                logger.info("Rolled back inventory updates")
            except Exception as e:
                logger.error(f"Failed to rollback inventory: {e}")
        
        # Note: Cart clearing rollback is not implemented as it's not critical
        # and the cart will be cleared on next successful payment anyway
        
    except Exception as e:
        logger.error(f"Error during rollback: {e}")

async def _rollback_inventory_updates(metadata: Dict[str, Any]):
    """Rollback inventory updates in case of order creation failure"""
    try:
        import json
        from ..services.odoo_service import execute_odoo_kw, get_product_by_id
        
        # Parse items from metadata
        items_json = metadata.get("items", "[]")
        items = json.loads(items_json)
        
        logger.info(f"Rolling back inventory for {len(items)} items")
        
        for item in items:
            product_id = item.get("id")
            quantity = item.get("quantity", 1)
            item_type = item.get("type", "odoo_product")
            
            if item_type == "odoo_product":
                try:
                    odoo_product_id = int(product_id)
                    product_data = await get_product_by_id(odoo_product_id)
                    if product_data:
                        current_quantity = product_data.get('qty_available', 0.0)
                        restored_quantity = current_quantity + quantity
                        
                        # Update stock quant back to original value
                        stock_location_id = 8
                        domain = [
                            ('product_id', '=', odoo_product_id),
                            ('location_id', '=', stock_location_id)
                        ]
                        
                        quant_ids = execute_odoo_kw('stock.quant', 'search', [domain], {'limit': 1})
                        
                        if quant_ids:
                            quant_id = quant_ids[0]
                            update_values = {'inventory_quantity': restored_quantity}
                            execute_odoo_kw('stock.quant', 'write', [[quant_id], update_values])
                            execute_odoo_kw('stock.quant', 'action_apply_inventory', [[quant_id]])
                            logger.info(f"Rolled back inventory for product {product_id}: {current_quantity} -> {restored_quantity}")
                        
                except Exception as e:
                    logger.error(f"Failed to rollback inventory for product {product_id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error rolling back inventory updates: {e}")
        raise
