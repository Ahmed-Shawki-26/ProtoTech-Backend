import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any

# Use absolute imports for robustness
from src.stripe_.config.config import settings
from src.auth.logging import logger 

def send_email(payment_details: Dict[str, Any], line_items: List[Dict[str, Any]]):
    """
    Sends a detailed, itemized payment confirmation email with both HTML and plain-text parts.

    Args:
        payment_details (Dict): The Stripe checkout session object.
        line_items (List[Dict]): The list of line items retrieved from Stripe.
    """
    # --- Extract data from the payment object ---
    user_email = payment_details.get("customer_details", {}).get("email")
    user_name = payment_details.get("customer_details", {}).get("name", "Valued Customer")
    amount_total = payment_details.get("amount_total", 0)
    currency = payment_details.get("currency", "usd").upper()
    order_id = payment_details.get("id")

    if not user_email:
        logger.error(f"Cannot send confirmation email for order {order_id}: User email is missing.")
        return

    subject = f"Your ProtoTech Order Confirmation ({order_id[-10:]})"

    # --- 1. Build the Plain-Text Part ---
    plain_text_body = f"""
Hi {user_name},

Thank you for your order! We've received your payment and are getting your order ready.

Order ID: {order_id}
"""
    
    if line_items and line_items.get('data'):
        plain_text_body += "\n--- Order Summary ---\n"
        for item in line_items['data']:
            product_name = item.get("description", "N/A")
            quantity = item.get("quantity")
            total_price = item.get("amount_total", 0) / 100
            plain_text_body += f"- {product_name} (x{quantity}): {total_price:.2f} {currency}\n"
    
    plain_text_body += f"\nGrand Total: {amount_total / 100:.2f} {currency}\n"
    plain_text_body += "\nIf you have any questions, please contact our support team.\n\nRegards,\nThe ProtoTech Team\n\nProtoTech Inc.\n123 Innovation Drive, Cairo, Egypt"


    # --- 2. Build the HTML Part ---
    items_html = ""
    if line_items and line_items.get('data'):
        items_html += """
        <tr style="background-color:#f2f2f2;">
            <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Product</th>
            <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Quantity</th>
            <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Unit Price</th>
            <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">Total</th>
        </tr>
        """
        for item in line_items['data']:
            product_name = item.get("description", "N/A")
            quantity = item.get("quantity")
            unit_price = item.get("price", {}).get("unit_amount", 0) / 100
            total_price = item.get("amount_total", 0) / 100
            
            items_html += f"""
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd;">{product_name}</td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{quantity}</td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{unit_price:.2f} {currency}</td>
                <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{total_price:.2f} {currency}</td>
            </tr>
            """

    # --- COMPLETE HTML BODY ---
    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Payment Confirmation</title>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #eee; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .header {{ font-size: 24px; font-weight: bold; color: #007bff; text-align: center; margin-bottom: 20px; }}
            .summary-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }}
            .total-row td {{ font-weight: bold; padding-top: 15px; border-top: 2px solid #333; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #777; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">Thank You For Your Order!</div>
            <p>Hi {user_name},</p>
            <p>We've received your payment and your order is now being processed. Here are the details:</p>
            <p><strong>Order ID:</strong> {order_id}</p>
            
            <table class="summary-table">
                {items_html}
                <tr class="total-row">
                    <td colspan="3" style="text-align: right; padding: 10px;">Grand Total:</td>
                    <td style="text-align: right; padding: 10px;">{amount_total / 100:.2f} {currency}</td>
                </tr>
            </table>

            <p>We'll notify you again once your order has shipped. If you have any questions, please don't hesitate to contact our support team.</p>
            <p>Regards,<br>The ProtoTech Team</p>
            <div class="footer">
                <p>&copy; 2024 ProtoTech. All rights reserved.</p>
                <p><strong>ProtoTech Inc.</strong><br>123 Innovation Drive, Cairo, Egypt</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # --- 3. Create a MIME multipart message ---
    msg = MIMEMultipart('alternative')
    # FIX: Use the correct settings variables from your stripe_/config/config.py
    msg["From"] = settings.MAIL_FROM
    msg["To"] = user_email
    msg["Subject"] = subject

    msg.attach(MIMEText(plain_text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    
    # --- 4. Send the Email ---
    try:
        # FIX: Use the correct settings variables (SMTP_HOST, SMTP_PORT, etc.)
        with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.SSL_PORT) as smtp:
            smtp.login(settings.MAIL_FROM, settings.MAIL_PASSWORD)
            smtp.send_message(msg)
            logger.info(f"✅ Detailed confirmation email sent to {user_email} for order {order_id}")
    except Exception as e:
        logger.error(f"❌ Failed to send confirmation email for order {order_id}: {e}")