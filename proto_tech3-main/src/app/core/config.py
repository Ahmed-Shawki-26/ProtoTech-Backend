
# /src/app/core/config.py

class Settings:
    # --- API Info ---
    API_TITLE: str = "ProtoTech PCB Pricing API"
    API_DESCRIPTION: str = "Upload a Gerber ZIP to render images, get dimensions, and calculate manufacturing price based on detailed rules."
    API_VERSION: str = "3.0.0"

    # --- 1. Base Defaults ---
    MAX_WIDTH_CM: float = 38.0
    MAX_HEIGHT_CM: float = 28.0

    # --- 2. Panel Pricing (per cm²) ---
    # The keys are the upper bound of the area in cm².
    PANEL_PRICE_BRACKETS_EGP: dict[int, float] = {
        1000: 1.6,
        1500: 1.5,
        2000: 1.4,
        2500: 1.3,
        3000: 1.2,
    }
    MINIMUM_CM2_PRICE_EGP: float = 1.2

    # --- 3. Quantity Multipliers ---
    # The keys are the lower bound of the quantity.
    QUANTITY_MULTIPLIERS: dict[int, float] = {
        5: 1.0,
        3: 1.5,
        1: 2.0,
    }

    # --- 4. Different Designs Multiplier ---
    DIFFERENT_DESIGNS_MULTIPLIER_FACTOR: float = 0.1

    # --- 5. Delivery Format (Panel by Customer) Multiplier ---
    PANEL_BY_CUSTOMER_MULTIPLIER_FACTOR: float = 0.1

    # --- 6. Thickness Multipliers (in mm) ---
    THICKNESS_MULTIPLIERS: dict[float, float] = {
        0.4: 1.4,
        0.6: 1.3,
        0.8: 1.2,
        1.0: 1.0,
        1.2: 1.0, # Adding 1.2mm explicitly as a standard option
        1.6: 1.0,
        2.0: 1.3,
    }
    
    # --- 7. Color Options ---
    GREEN_COLOR_MULTIPLIER: float = 1.0
    OTHER_COLOR_MULTIPLIER: float = 1.2
    OTHER_COLOR_EXTRA_DAYS: int = 1

    # --- 8. High-Spec Options ---
    OUTER_COPPER_WEIGHT_MULTIPLIERS: dict[str, float] = {
        "1 oz": 1.0,
        "2 oz": 2.5,
    }
    
    # This is a simplified check. We assume the first number is the hole size.
    MIN_VIA_HOLE_THRESHOLD_MM: float = 0.3
    MIN_VIA_HOLE_MULTIPLIER: float = 1.3
    
    BOARD_OUTLINE_TOLERANCE_MULTIPLIERS: dict[str, float] = {
        "±0.2mm (Regular)": 1.0,
        "±0.1mm (Precision)": 1.3,
    }

settings = Settings()