# /src/email_service.py

import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from typing import Dict
from .logging import logger
from dotenv import load_dotenv

load_dotenv()

# ... (ConnectionConfig remains the same) ...
conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "test@example.com"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "password"),
    MAIL_FROM = os.getenv("MAIL_FROM", "test@example.com"),
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

# Toggle real email sending. In local/dev environments, leave EMAIL_ENABLED unset or set to "false"
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"


async def send_verification_email(recipient_email: str, verification_link: str, first_name: str):
    """
    Sends a styled HTML verification email to a new user.

    Args:
        recipient_email (str): The email address of the recipient.
        verification_link (str): The URL the user will click to verify their account.
        first_name (str): The first name of the user, for personalization.
    """
    # --- UPDATED: HTML Template with Hover Effect for the Button ---
    template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Verify Your Email Address</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                margin: 20px 0;
                background-color: #007bff; /* --- Default Blue Color --- */
                color: #ffffff !important; /* !important to override default link color */
                text-decoration: none;
                border-radius: 5px;
                font-size: 16px;
                transition: background-color 0.3s ease; /* Smooth transition */
            }}
            /* --- NEW: Style for when the user hovers over the button --- */
            .button:hover {{
                background-color: #0056b3; /* --- Darker Blue on Hover --- */
            }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Welcome to Our App!</h2>
            <p>Hello {first_name},</p>
            <p>Thank you for registering. Please click the button below to verify your email address and complete your registration.</p>
            <!-- Note: The color is white, but some email clients might override it. 
                 The `!important` in the CSS helps prevent this. -->
            <a href="{verification_link}" class="button" style="color: #ffffff;">Verify Email Address</a>
            <p>If the button above doesn't work, you can also copy and paste the following link into your browser:</p>
            <p><a href="{verification_link}">{verification_link}</a></p>
            <p>If you did not register for this account, you can safely ignore this email.</p>
            <div class="footer">
                <p>© 2024 Your Cool App. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Verify Your Email Address for Our App",
        recipients=[recipient_email],
        body=template,
        subtype="html"
    )

    # In development, don't attempt to send real emails; just log the link
    if not EMAIL_ENABLED:
        logger.info(
            "EMAIL_ENABLED is false; skipping real email send. Verification link for %s: %s",
            recipient_email,
            verification_link,
        )
        return

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"Verification email sent successfully to {recipient_email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {recipient_email}: {e}")
        raise

async def send_payment_confirmation_email(recipient_email: str, order_data: Dict):
    """
    Sends a styled HTML payment confirmation email.

    Args:
        recipient_email (str): The email address of the recipient.
        order_data (Dict): Dictionary containing order details.
    """
    template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Payment Confirmation - ProtoTech</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
            .header {{ background-color: #28a745; color: white; padding: 20px; border-radius: 5px; text-align: center; }}
            .order-details {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .amount {{ font-size: 24px; font-weight: bold; color: #28a745; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #777; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Payment Confirmation</h1>
            </div>
            <p>Hello {order_data.get('customer_name', 'Customer')},</p>
            <p>Thank you for your payment! Your order has been successfully processed.</p>
            
            <div class="order-details">
                <h3>Order Details:</h3>
                <p><strong>Order ID:</strong> {order_data.get('order_id', 'N/A')}</p>
                <p><strong>Amount:</strong> <span class="amount">{order_data.get('amount', 'N/A')}</span></p>
                <p><strong>Currency:</strong> {order_data.get('currency', 'N/A')}</p>
                <p><strong>Payment ID:</strong> {order_data.get('payment_intent_id', 'N/A')}</p>
            </div>
            
            <p>We'll start processing your order right away. You'll receive updates on your order status via email.</p>
            <p>If you have any questions, please don't hesitate to contact our support team.</p>
            
            <div class="footer">
                <p>© 2024 ProtoTech Manufacturing. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="✅ Payment Confirmation - ProtoTech",
        recipients=[recipient_email],
        body=template,
        subtype="html"
    )

    # In development, don't attempt to send real emails; just log
    if not EMAIL_ENABLED:
        logger.info(
            "EMAIL_ENABLED is false; skipping real email send. Payment confirmation for %s: Order %s",
            recipient_email,
            order_data.get('order_id', 'N/A'),
        )
        return

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"Payment confirmation email sent successfully to {recipient_email}")
    except Exception as e:
        logger.error(f"Failed to send payment confirmation email to {recipient_email}: {e}")
        raise

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        logger.info(f"Verification email sent to {recipient_email}")
    except Exception as e:
        # Do not break user registration on email failure. Log and continue.
        logger.error(f"Failed to send verification email to {recipient_email}: {e}")
        return


async def send_password_reset_email(recipient_email: str, reset_link: str, first_name: str):
    """
    Sends a styled HTML password reset email to a user.

    Args:
        recipient_email (str): The email address of the recipient.
        reset_link (str): The URL the user will click to reset their password.
        first_name (str): The first name of the user, for personalization.
    """
    template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Reset Your Password</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
            .button {{
                display: inline-block; padding: 12px 24px; margin: 20px 0;
                background-color: #dc3545; color: #ffffff !important;
                text-decoration: none; border-radius: 5px; font-size: 16px;
                transition: background-color 0.3s ease;
            }}
            .button:hover {{ background-color: #c82333; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Password Reset Request</h2>
            <p>Hello {first_name},</p>
            <p>We received a request to reset the password for your account. Please click the button below to set a new password. This link is valid for 1 hour.</p>
            <a href="{reset_link}" class="button" style="color: #ffffff;">Reset Password</a>
            <p>If you did not request a password reset, you can safely ignore this email. Your password will not be changed.</p>
            <div class="footer">
                <p>© 2024 Your Cool App. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Your Password Reset Request",
        recipients=[recipient_email],
        body=template,
        subtype="html"
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        logger.info(f"Password reset email sent to {recipient_email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email to {recipient_email}: {e}")
        # Don't re-raise the error to the user, just log it.
        # This prevents leaking information about whether an email exists.