# Local Pricing Service for FR-4 PCB Manufacturing
# Based on pricing rules from proto_tech2-main

from typing import Dict, Any, Optional
from app.schemas.pcb import ManufacturingParameters, BoardDimensions, BaseMaterial
from app.core.exceptions import PricingError, ErrorCode, raise_pricing_error
from app.services.parameter_normalizer import ParameterNormalizer
from app.utils.enum_helpers import get_thickness_value, safe_thickness_compare, get_thickness_multiplier
import logging

logger = logging.getLogger(__name__)

class LocalPricingService:
    """
    Local PCB Pricing Service for all materials (FR-4, Flex, Aluminum)
    Implements the pricing rules from proto_tech2-main for local manufacturing
    
    Quantity Rules:
    - FR-4: Uses specific quantity multipliers (5: 1.0x, 3: 1.5x, 1: 2.0x)
    - Flex & Aluminum: Normal quantity pricing (no special multipliers)
    """
    
    # Material-specific base multipliers
    MATERIAL_BASE_MULTIPLIERS = {
        BaseMaterial.fr4: 1.0,
        BaseMaterial.flex: 2.5,  # Flex PCBs are more expensive
        BaseMaterial.aluminum: 3.0,  # Aluminum PCBs are more expensive
        BaseMaterial.copper_core: 2.8,
        BaseMaterial.rogers: 4.0,
        BaseMaterial.ptfe_teflon: 5.0,
    }
    
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
        "0.2mm": 1.0,
        "±0.2mm": 1.0,
        "±0.2mm (Regular)": 1.0,
        "0.1mm": 1.3,
        "±0.1mm": 1.3,
        "±0.1mm (Precision)": 1.3,
    }
    
    # Fixed Engineering Fees for Local Manufacturing
    FIXED_ENGINEERING_FEES_EGP: float = 200.0
    
    # Tax Rate for Local Manufacturing
    TAX_RATE: float = 0.14  # 14%
    
    @classmethod
    def _safe_get_param(cls, params: ManufacturingParameters, attr_name: str, default_value: Any = None) -> Any:
        """
        Safely get parameter value, return default if not found or invalid.
        This prevents crashes when Flex/Aluminum parameters are missing.
        """
        try:
            value = getattr(params, attr_name, default_value)
            return value if value is not None else default_value
        except (AttributeError, TypeError):
            return default_value
    
    @classmethod
    def calculate_local_price(
        cls, 
        dimensions: BoardDimensions, 
        params: ManufacturingParameters
    ) -> Dict[str, Any]:
        """
        Calculate local PCB manufacturing price for all materials (FR-4, Flex, Aluminum)
        based on proto_tech2-main rules with material-specific adjustments
        """
        # DEBUG: Log entry point with detailed parameter info
        logger.warning(f"DEBUG: calculate_local_price called")
        logger.warning(f"DEBUG: dimensions = {dimensions}")
        logger.warning(f"DEBUG: params type = {type(params)}")
        logger.warning(f"DEBUG: thickness type = {type(params.pcb_thickness_mm)}")
        logger.warning(f"DEBUG: thickness value = {params.pcb_thickness_mm}")
        
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
        
        # Rule 4: Different Designs Multiplier (safe parameter handling)
        designs = cls._safe_get_param(params, 'different_designs', 1)
        designs_multiplier = 1.0 + (designs - 1) * cls.DIFFERENT_DESIGNS_MULTIPLIER_FACTOR
        multipliers['designs'] = designs_multiplier
        
        # Rule 5: Delivery Format Multiplier (safe parameter handling)
        delivery_multiplier = 1.0
        delivery_format = cls._safe_get_param(params, 'delivery_format', 'Single PCB')
        if delivery_format == "Panel by Customer":
            delivery_multiplier = 1.0 + (designs - 1) * cls.PANEL_BY_CUSTOMER_MULTIPLIER_FACTOR
        multipliers['delivery_format'] = delivery_multiplier
        
        # Rule 6: Thickness Multiplier
        thickness = params.pcb_thickness_mm
        
        # DEBUG: Log thickness type and value
        logger.warning(f"DEBUG: thickness type = {type(thickness)}")
        logger.warning(f"DEBUG: thickness value = {thickness}")
        
        # Convert thickness enum to float for comparison using safe helper
        thickness_value = get_thickness_value(thickness)
        logger.warning(f"DEBUG: converted thickness = {thickness_value}, type = {type(thickness_value)}")
        
        # Special handling for Flex material - only supports 0.12mm
        if params.base_material == BaseMaterial.flex:
            # Flex always uses 0.12mm (default thickness), no extra cost
            thickness_multiplier = 1.0  # No extra cost for Flex default thickness
        elif safe_thickness_compare(thickness_value, 1.0, '>=') and safe_thickness_compare(thickness_value, 1.6, '<='):
            thickness_multiplier = 1.0
        else:
            thickness_multiplier = get_thickness_multiplier(thickness_value, cls.THICKNESS_MULTIPLIERS)
            
        multipliers['thickness'] = thickness_multiplier
        
        # Rule 7: Color Options (safe parameter handling with enum support)
        pcb_color = cls._safe_get_param(params, 'pcb_color', 'green')
        # Handle both string and enum values
        color_str = str(pcb_color).lower() if pcb_color else 'green'
        
        # Special handling for Flex material - Yellow is default and only color
        if params.base_material == BaseMaterial.flex:
            # Flex always uses Yellow (default color), no extra cost or days
            color_multiplier = cls.GREEN_COLOR_MULTIPLIER  # Same as green (no extra cost)
            extra_days = 0  # No extra working days for Flex yellow
        # Special handling for Aluminum material - White is default and standard color
        elif params.base_material == BaseMaterial.aluminum and 'white' in color_str:
            # Aluminum with White is the standard configuration, no extra cost or days
            color_multiplier = cls.GREEN_COLOR_MULTIPLIER  # Same as green (no extra cost)
            extra_days = 0  # No extra working days for Aluminum white
        elif 'green' in color_str:
            color_multiplier = cls.GREEN_COLOR_MULTIPLIER
        else:
            color_multiplier = cls.OTHER_COLOR_MULTIPLIER
            extra_days = cls.OTHER_COLOR_EXTRA_DAYS
            
        multipliers['color'] = color_multiplier
        
        # Rule 8: High-Spec Options (safe parameter handling)
        # Copper Weight
        copper_weight = cls._safe_get_param(params, 'outer_copper_weight', '1 oz')
        copper_multiplier = cls.OUTER_COPPER_WEIGHT_MULTIPLIERS.get(copper_weight, 1.0)
        multipliers['copper_weight'] = copper_multiplier
        
        # Via Hole - Using ParameterNormalizer for robust handling
        via_multiplier = 1.0
        try:
            min_via_value = cls._safe_get_param(params, 'min_via_hole_size_dia', 0.3)
            # Use ParameterNormalizer for consistent handling
            min_via_enum = ParameterNormalizer.normalize_via_hole(min_via_value)
            min_via_float = float(min_via_enum.value.replace('mm', ''))
            
            if min_via_float < cls.MIN_VIA_HOLE_THRESHOLD_MM:
                via_multiplier = cls.MIN_VIA_HOLE_MULTIPLIER
                
        except Exception as e:
            logger.warning(f"Failed to process via hole parameter: {e}")
            # Use default value and continue
            min_via_float = 0.3
        multipliers['via_hole'] = via_multiplier
        
        # Tolerance (robust handling for enum values)
        tolerance = cls._safe_get_param(params, 'board_outline_tolerance', '±0.2mm (Regular)')
        # Handle both enum and string values
        tolerance_str = str(tolerance) if tolerance else '±0.2mm (Regular)'
        tolerance_multiplier = cls.BOARD_OUTLINE_TOLERANCE_MULTIPLIERS.get(tolerance_str, 1.0)
        multipliers['tolerance'] = tolerance_multiplier
        
        # Final Price Calculation
        final_price = base_price
        for key, value in multipliers.items():
            final_price *= value
        
        # Apply material-specific multiplier (Flex=2.5x, Aluminum=3.0x, etc.)
        material_multiplier = cls.MATERIAL_BASE_MULTIPLIERS.get(params.base_material, 1.0)
        final_price *= material_multiplier
        
        # Apply quantity multiplier at the end (as per the rules)
        # FR-4 has specific quantity rules, while Flex and Aluminum use normal quantity pricing
        if params.base_material == BaseMaterial.fr4:
            # FR-4 specific quantity multipliers
            quantity_multiplier = 1.0
            for quantity_threshold, multiplier in sorted(cls.QUANTITY_MULTIPLIERS.items(), reverse=True):
                if params.quantity >= quantity_threshold:
                    quantity_multiplier = multiplier
                    break
            final_price = final_price * quantity_multiplier * params.quantity
        else:
            # Flex and Aluminum use normal quantity pricing (no special multipliers)
            quantity_multiplier = 1.0
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
                "material": str(params.base_material),
                "material_multiplier": material_multiplier,
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
            "quantity_rules": {
                "fr4": cls.QUANTITY_MULTIPLIERS,
                "flex_aluminum": {"note": "Normal quantity pricing (no special multipliers)"}
            },
            "thickness_rules": cls.THICKNESS_MULTIPLIERS,
            "color_rules": {
                "green": {"multiplier": cls.GREEN_COLOR_MULTIPLIER, "extra_days": 0},
                "flex_yellow": {"multiplier": cls.GREEN_COLOR_MULTIPLIER, "extra_days": 0, "note": "Standard color for Flex material"},
                "aluminum_white": {"multiplier": cls.GREEN_COLOR_MULTIPLIER, "extra_days": 0, "note": "Standard color for Aluminum material"},
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
