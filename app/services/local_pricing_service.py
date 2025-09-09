# Local Pricing Service for FR-4 PCB Manufacturing
# Based on pricing rules from proto_tech2-main

from typing import Dict, Any, Optional
from app.schemas.pcb import ManufacturingParameters, BoardDimensions

class LocalPricingService:
    """
    Local FR-4 PCB Pricing Service
    Implements the pricing rules from proto_tech2-main for local manufacturing
    """
    
    # Base Defaults
    MAX_WIDTH_CM: float = 38.0
    MAX_HEIGHT_CM: float = 28.0
    
    # Panel Pricing (per cm²)
    PANEL_PRICE_BRACKETS_EGP: Dict[int, float] = {
        1000: 1.6,
        1500: 1.5,
        2000: 1.4,
        2500: 1.3,
        3000: 1.2,
    }
    MINIMUM_CM2_PRICE_EGP: float = 1.2
    
    # Quantity Multipliers
    QUANTITY_MULTIPLIERS: Dict[int, float] = {
        5: 1.0,
        3: 1.5,
        1: 2.0,
    }
    
    # Different Designs Multiplier
    DIFFERENT_DESIGNS_MULTIPLIER_FACTOR: float = 0.1
    
    # Delivery Format Multiplier
    PANEL_BY_CUSTOMER_MULTIPLIER_FACTOR: float = 0.1
    
    # Thickness Multipliers (in mm)
    THICKNESS_MULTIPLIERS: Dict[float, float] = {
        0.4: 1.4,
        0.6: 1.3,
        0.8: 1.2,
        1.0: 1.0,
        1.2: 1.0,
        1.6: 1.0,
        2.0: 1.3,
    }
    
    # Color Options
    GREEN_COLOR_MULTIPLIER: float = 1.0
    OTHER_COLOR_MULTIPLIER: float = 1.2
    OTHER_COLOR_EXTRA_DAYS: int = 1
    
    # High-Spec Options
    OUTER_COPPER_WEIGHT_MULTIPLIERS: Dict[str, float] = {
        "1 oz": 1.0,
        "2 oz": 2.5,
    }
    
    MIN_VIA_HOLE_THRESHOLD_MM: float = 0.3
    MIN_VIA_HOLE_MULTIPLIER: float = 1.3
    
    BOARD_OUTLINE_TOLERANCE_MULTIPLIERS: Dict[str, float] = {
        "±0.2mm (Regular)": 1.0,
        "±0.1mm (Precision)": 1.3,
    }
    
    # Fixed Engineering Fees for Local Manufacturing
    FIXED_ENGINEERING_FEES_EGP: float = 200.0
    
    # Tax Rate for Local Manufacturing
    TAX_RATE: float = 0.14  # 14%
    
    @classmethod
    def calculate_local_price(
        cls, 
        dimensions: BoardDimensions, 
        params: ManufacturingParameters
    ) -> Dict[str, Any]:
        """
        Calculate local FR-4 PCB manufacturing price based on proto_tech2-main rules
        """
        # Initialize variables
        multipliers = {}
        width_cm = dimensions.width_mm / 10.0
        height_cm = dimensions.height_mm / 10.0
        extra_days = 0
        
        # Rule 1: Base Defaults (Dimension Check)
        if (width_cm > cls.MAX_WIDTH_CM and height_cm > cls.MAX_HEIGHT_CM) or \
           (width_cm > cls.MAX_HEIGHT_CM and height_cm > cls.MAX_WIDTH_CM):
            raise ValueError(
                f"Board dimensions ({width_cm:.1f}x{height_cm:.1f} cm) exceed the maximum "
                f"allowed size of {cls.MAX_WIDTH_CM}x{cls.MAX_HEIGHT_CM} cm."
            )
        
        # Rule 2: Panel Pricing
        panel_area_cm2 = width_cm * height_cm
        price_per_cm2 = cls.MINIMUM_CM2_PRICE_EGP
        
        for area_threshold, price in sorted(cls.PANEL_PRICE_BRACKETS_EGP.items()):
            if panel_area_cm2 <= area_threshold:
                price_per_cm2 = price
                break
        
        base_price = panel_area_cm2 * price_per_cm2
        
        # Rule 3: Quantity Multiplier (applied at the end, not in multipliers)
        # multipliers['quantity'] = 1.0
        
        # Rule 4: Different Designs Multiplier
        designs = params.different_designs
        designs_multiplier = 1.0 + (designs - 1) * cls.DIFFERENT_DESIGNS_MULTIPLIER_FACTOR
        multipliers['designs'] = designs_multiplier
        
        # Rule 5: Delivery Format Multiplier
        delivery_multiplier = 1.0
        if params.delivery_format == "Panel by Customer":
            delivery_multiplier = 1.0 + (designs - 1) * cls.PANEL_BY_CUSTOMER_MULTIPLIER_FACTOR
        multipliers['delivery_format'] = delivery_multiplier
        
        # Rule 6: Thickness Multiplier
        thickness = params.pcb_thickness_mm
        if 1.0 <= thickness <= 1.6:
            thickness_multiplier = 1.0
        else:
            thickness_multiplier = cls.THICKNESS_MULTIPLIERS.get(thickness, 1.0)
        multipliers['thickness'] = thickness_multiplier
        
        # Rule 7: Color Options
        if params.pcb_color.lower() == "green":
            color_multiplier = cls.GREEN_COLOR_MULTIPLIER
        else:
            color_multiplier = cls.OTHER_COLOR_MULTIPLIER
            extra_days = cls.OTHER_COLOR_EXTRA_DAYS
        multipliers['color'] = color_multiplier
        
        # Rule 8: High-Spec Options
        # Copper Weight
        copper_weight = params.outer_copper_weight
        copper_multiplier = cls.OUTER_COPPER_WEIGHT_MULTIPLIERS.get(copper_weight, 1.0)
        multipliers['copper_weight'] = copper_multiplier
        
        # Via Hole
        via_multiplier = 1.0
        try:
            min_via_str = params.min_via_hole_size_dia
            # Extract first number from string like "0.3mm/(0.4/0.45mm)"
            min_via_float = float(min_via_str.split('mm')[0])
            if min_via_float < cls.MIN_VIA_HOLE_THRESHOLD_MM:
                via_multiplier = cls.MIN_VIA_HOLE_MULTIPLIER
        except (ValueError, IndexError):
            pass
        multipliers['via_hole'] = via_multiplier
        
        # Tolerance
        tolerance = params.board_outline_tolerance
        tolerance_multiplier = cls.BOARD_OUTLINE_TOLERANCE_MULTIPLIERS.get(tolerance, 1.0)
        multipliers['tolerance'] = tolerance_multiplier
        
        # Final Price Calculation
        final_price = base_price
        for key, value in multipliers.items():
            final_price *= value
        
        # Apply quantity multiplier at the end (as per the rules)
        quantity_multiplier = 1.0
        for quantity_threshold, multiplier in sorted(cls.QUANTITY_MULTIPLIERS.items(), reverse=True):
            if params.quantity >= quantity_threshold:
                quantity_multiplier = multiplier
                break
        final_price = final_price * quantity_multiplier * params.quantity
        
        # Store the price before tax for the breakdown
        price_before_tax = final_price
        
        # Apply 14% tax to the final price
        tax_amount = final_price * cls.TAX_RATE
        final_price_with_tax = final_price + tax_amount
        
        # Add fixed engineering fees for local manufacturing
        engineering_fees_egp = cls.FIXED_ENGINEERING_FEES_EGP
        final_price_with_engineering = final_price_with_tax + engineering_fees_egp
        
        return {
            "final_price_egp": round(final_price_with_engineering, 2),
            "extra_working_days": extra_days,
            "details": {
                "base_price_egp": round(base_price, 2),
                "price_after_multipliers_egp": round(final_price / (quantity_multiplier * params.quantity), 2),
                "cost_after_multipliers_total_quantity_egp": round(price_before_tax, 2),
                "panel_area_cm2": round(panel_area_cm2, 2),
                "price_per_cm2_egp": price_per_cm2,
                "applied_multipliers": multipliers,
                "tax_amount_egp": round(tax_amount, 2),
                "engineering_fees_egp": engineering_fees_egp,
                "dimensions_cm": {
                    "width": round(width_cm, 2),
                    "height": round(height_cm, 2)
                }
            }
        }
    
    @classmethod
    def get_pricing_info(cls) -> Dict[str, Any]:
        """
        Get pricing information for display purposes
        """
        return {
            "base": {
                "dimension_limit_cm": {
                    "max_width": cls.MAX_WIDTH_CM,
                    "max_height": cls.MAX_HEIGHT_CM
                }
            },
            "panel_pricing": {
                "unit_cm2_price": cls.PANEL_PRICE_BRACKETS_EGP,
                "minimum_cm2_price": cls.MINIMUM_CM2_PRICE_EGP,
                "note": "Panel area is width_cm × height_cm. Pricing is capped at minimum 1.2 EGP/cm²."
            },
            "quantity_rules": cls.QUANTITY_MULTIPLIERS,
            "thickness_rules": cls.THICKNESS_MULTIPLIERS,
            "color_rules": {
                "green": {"multiplier": cls.GREEN_COLOR_MULTIPLIER, "extra_days": 0},
                "other": {"multiplier": cls.OTHER_COLOR_MULTIPLIER, "extra_days": cls.OTHER_COLOR_EXTRA_DAYS}
            },
            "high_spec_options": {
                "outer_copper_weight": cls.OUTER_COPPER_WEIGHT_MULTIPLIERS,
                "min_via_hole_mm": {
                    "0.3": 1.0,
                    "<0.3": cls.MIN_VIA_HOLE_MULTIPLIER
                },
                "board_outline_tolerance_mm": {
                    "0.2": 1.0,
                    "0.1": cls.BOARD_OUTLINE_TOLERANCE_MULTIPLIERS["±0.1mm (Precision)"]
                }
            }
        }
