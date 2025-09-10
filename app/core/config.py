# app/core/config.py
from ..utils.egp_yuan import get_exchange_rate_egp_cny
import os

class Settings:
    # --- API Info ---
    API_TITLE: str = "ProtoTech Manufacturing API"
    API_DESCRIPTION: str = "Complete manufacturing platform for PCB production, 3D printing, user management, and e-commerce functionality."
    API_VERSION: str = "2.0.0"
    
    # --- Server Configuration ---
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # --- Pricing Model Configuration ---
    # Exchange Rates and Fees
    YUAN_TO_EGP_RATE: float = get_exchange_rate_egp_cny() # IMPORTANT: Update this with the current rate
    EXCHANGE_RATE_BUFFER: float = 1.05  # 5% buffer on exchange rate

    # Direct Cost Formula
    FIXED_ENGINEERING_FEE_YUAN: float = 50.0
    PRICE_PER_M2_YUAN: float = 480.0

    # Shipping Cost Formula
    DEFAULT_SHIPPING_THICKNESS_MM: float = 1.6
    SHIPPING_RATIO: float = 3.0
    SHIPPING_COST_PER_KG_YUAN: float = 60.0

    # Final Price Multipliers
    CUSTOMS_RATE_MULTIPLIER: float = 1.6
    FINAL_PRICE_MULTIPLIER_DEFAULT: float = 1.6
    FINAL_PRICE_MULTIPLIER_MID_AREA: float = 1.5  # For area >= 0.5 m^2
    FINAL_PRICE_MULTIPLIER_LARGE_AREA: float = 1.4 # For area >= 1.0 m^2
    FR4_DENSITY_G_PER_CM3: float = 1.85

    # Add missing environment variables for e-commerce
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_SUCCESS_URL: str = os.getenv("STRIPE_SUCCESS_URL", "https://proto-tech-frontend.vercel.app/confirmation")
    STRIPE_CANCEL_URL: str = os.getenv("STRIPE_CANCEL_URL", "https://proto-tech-frontend.vercel.app/cart")
    STRIPE_CURRENCY: str = os.getenv("STRIPE_CURRENCY", "egp")

    # Odoo configuration
    ODOO_URL: str = os.getenv("ODOO_URL", "http://localhost:8069")
    ODOO_DB: str = os.getenv("ODOO_DB", "test")
    ODOO_USERNAME: str = os.getenv("ODOO_USERNAME", "admin")
    ODOO_PASSWORD: str = os.getenv("ODOO_PASSWORD", "admin")

    # E-commerce mock mode
    ECOMMERCE_MOCK: bool = os.getenv("ECOMMERCE_MOCK", "0") == "1"

settings = Settings()