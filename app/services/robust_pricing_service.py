# app/services/robust_pricing_service.py

import logging
from typing import Dict, Any, Optional, Union
from app.schemas.pcb import ManufacturingParameters, BoardDimensions, BaseMaterial
from app.services.local_pricing_service import LocalPricingService
from app.services.price_calculator import PriceCalculator

# Set up logging
logger = logging.getLogger(__name__)

class RobustPricingService:
    """
    Robust pricing service that handles all PCB materials gracefully.
    Prevents crashes by providing fallback pricing when parameters are missing or unrecognized.
    """
    
    # Material-specific pricing multipliers
    MATERIAL_MULTIPLIERS = {
        BaseMaterial.fr4: 1.0,
        BaseMaterial.flex: 2.5,  # Flex PCBs are more expensive
        BaseMaterial.aluminum: 3.0,  # Aluminum PCBs are more expensive
        BaseMaterial.copper_core: 2.8,
        BaseMaterial.rogers: 4.0,
        BaseMaterial.ptfe_teflon: 5.0,
    }
    
    # Material-specific density (g/cm³) for weight calculations
    MATERIAL_DENSITIES = {
        BaseMaterial.fr4: 1.85,  # Standard FR-4 density
        BaseMaterial.flex: 1.4,  # Flex PCB density
        BaseMaterial.aluminum: 2.7,  # Aluminum density
        BaseMaterial.copper_core: 8.9,  # Copper density
        BaseMaterial.rogers: 1.9,  # Rogers material density
        BaseMaterial.ptfe_teflon: 2.2,  # PTFE density
    }
    
    @classmethod
    def safe_get_attribute(cls, obj: Any, attr_name: str, default_value: Any = None) -> Any:
        """
        Safely get an attribute from an object, returning default if not found or if it causes an error.
        
        Args:
            obj: The object to get the attribute from
            attr_name: The attribute name to get
            default_value: Default value if attribute is not found or causes error
            
        Returns:
            The attribute value or default_value
        """
        try:
            if hasattr(obj, attr_name):
                value = getattr(obj, attr_name)
                logger.debug(f"Successfully retrieved {attr_name}: {value}")
                return value
            else:
                logger.warning(f"Attribute {attr_name} not found, using default: {default_value}")
                return default_value
        except Exception as e:
            logger.warning(f"Error retrieving {attr_name}: {e}, using default: {default_value}")
            return default_value
    
    @classmethod
    def safe_get_dict_value(cls, dictionary: Dict, key: str, default_value: Any = None) -> Any:
        """
        Safely get a value from a dictionary, returning default if key not found.
        
        Args:
            dictionary: The dictionary to get the value from
            key: The key to look for
            default_value: Default value if key is not found
            
        Returns:
            The dictionary value or default_value
        """
        try:
            if key in dictionary:
                value = dictionary[key]
                logger.debug(f"Successfully retrieved {key}: {value}")
                return value
            else:
                logger.warning(f"Key {key} not found in dictionary, using default: {default_value}")
                return default_value
        except Exception as e:
            logger.warning(f"Error retrieving {key} from dictionary: {e}, using default: {default_value}")
            return default_value
    
    @classmethod
    def calculate_robust_price(
        cls, 
        dimensions: BoardDimensions, 
        params: ManufacturingParameters
    ) -> Dict[str, Any]:
        """
        Calculate price with robust error handling for all materials.
        
        Args:
            dimensions: PCB dimensions
            params: Manufacturing parameters
            
        Returns:
            Price calculation result with fallback handling
        """
        try:
            logger.info(f"Calculating price for material: {params.base_material}")
            
            # Use local pricing for ALL materials (FR-4, Flex, Aluminum)
            logger.info(f"Using local pricing for {params.base_material}")
            return cls._calculate_local_price_safe(dimensions, params)
                
        except Exception as e:
            logger.error(f"Critical error in price calculation: {e}")
            return cls._calculate_fallback_price(dimensions, params, str(e))
    
    @classmethod
    def _calculate_local_price_safe(cls, dimensions: BoardDimensions, params: ManufacturingParameters) -> Dict[str, Any]:
        """
        Safely calculate local FR-4 price with error handling.
        """
        try:
            # Use the existing local pricing service
            result = LocalPricingService.calculate_local_price(dimensions, params)
            logger.info("Local pricing calculation successful")
            return result
        except Exception as e:
            logger.error(f"Local pricing failed: {e}, falling back to basic calculation")
            return cls._calculate_fallback_price(dimensions, params, f"Local pricing error: {e}")
    
    @classmethod
    def _calculate_outsource_price_safe(cls, dimensions: BoardDimensions, params: ManufacturingParameters) -> Dict[str, Any]:
        """
        Safely calculate outsource price for non-FR-4 materials with error handling.
        """
        try:
            # Create a price calculator instance
            calculator = PriceCalculator()
            
            # Calculate base price
            base_quote = calculator.calculate_price(dimensions, params)
            
            # Apply material-specific multiplier
            material_multiplier = cls.safe_get_dict_value(
                cls.MATERIAL_MULTIPLIERS, 
                params.base_material, 
                1.0
            )
            
            # Calculate final price with material multiplier
            final_price_egp = base_quote.final_price_egp * material_multiplier
            
            logger.info(f"Outsource pricing calculation successful for {params.base_material}")
            
            return {
                "final_price_egp": round(final_price_egp, 2),
                "extra_working_days": 0,
                "details": {
                    "base_price_egp": round(base_quote.direct_cost_egp, 2),
                    "shipping_cost_egp": round(base_quote.shipping_cost_egp, 2),
                    "customs_rate_egp": round(base_quote.customs_rate_egp, 2),
                    "material_multiplier": material_multiplier,
                    "material": params.base_material,
                    "dimensions_cm": {
                        "width": round(dimensions.width_mm / 10.0, 2),
                        "height": round(dimensions.height_mm / 10.0, 2)
                    },
                    "original_quote_details": base_quote.details
                }
            }
            
        except Exception as e:
            logger.error(f"Outsource pricing failed: {e}, falling back to basic calculation")
            return cls._calculate_fallback_price(dimensions, params, f"Outsource pricing error: {e}")
    
    @classmethod
    def _calculate_fallback_price(cls, dimensions: BoardDimensions, params: ManufacturingParameters, error_message: str) -> Dict[str, Any]:
        """
        Calculate a basic fallback price when all else fails.
        This ensures the system never crashes due to pricing issues.
        """
        try:
            logger.warning(f"Using fallback pricing due to: {error_message}")
            
            # Basic area-based calculation
            area_cm2 = (dimensions.width_mm * dimensions.height_mm) / 100.0
            
            # Base price per cm² (conservative estimate)
            base_price_per_cm2 = 2.0  # EGP per cm²
            
            # Material multiplier
            material_multiplier = cls.safe_get_dict_value(
                cls.MATERIAL_MULTIPLIERS, 
                params.base_material, 
                1.0
            )
            
            # Quantity multiplier (basic)
            quantity_multiplier = cls.safe_get_attribute(params, 'quantity', 1)
            if quantity_multiplier <= 1:
                qty_mult = 2.0
            elif quantity_multiplier <= 3:
                qty_mult = 1.5
            else:
                qty_mult = 1.0
            
            # Calculate final price
            base_price = area_cm2 * base_price_per_cm2
            final_price = base_price * material_multiplier * qty_mult * quantity_multiplier
            
            # Add 14% tax
            tax_amount = final_price * 0.14
            final_price_with_tax = final_price + tax_amount
            
            # Add engineering fees
            engineering_fees = 200.0
            final_price_with_engineering = final_price_with_tax + engineering_fees
            
            logger.info(f"Fallback pricing calculation completed: {final_price_with_engineering:.2f} EGP")
            
            return {
                "final_price_egp": round(final_price_with_engineering, 2),
                "extra_working_days": 0,
                "details": {
                    "base_price_egp": round(base_price, 2),
                    "material_multiplier": material_multiplier,
                    "quantity_multiplier": qty_mult,
                    "tax_amount_egp": round(tax_amount, 2),
                    "engineering_fees_egp": engineering_fees,
                    "area_cm2": round(area_cm2, 2),
                    "price_per_cm2_egp": base_price_per_cm2,
                    "material": params.base_material,
                    "dimensions_cm": {
                        "width": round(dimensions.width_mm / 10.0, 2),
                        "height": round(dimensions.height_mm / 10.0, 2)
                    },
                    "fallback_reason": error_message,
                    "note": "This is a fallback price calculation due to pricing system limitations"
                }
            }
            
        except Exception as e:
            logger.critical(f"Even fallback pricing failed: {e}")
            # Ultimate fallback - return a basic price
            return {
                "final_price_egp": 500.0,  # Basic minimum price
                "extra_working_days": 0,
                "details": {
                    "base_price_egp": 400.0,
                    "material_multiplier": 1.0,
                    "quantity_multiplier": 1.0,
                    "tax_amount_egp": 50.0,
                    "engineering_fees_egp": 50.0,
                    "area_cm2": 0.0,
                    "price_per_cm2_egp": 0.0,
                    "material": str(params.base_material),
                    "dimensions_cm": {
                        "width": 0.0,
                        "height": 0.0
                    },
                    "fallback_reason": f"Critical pricing failure: {error_message}",
                    "note": "This is an emergency fallback price. Please contact support."
                }
            }
    
    @classmethod
    def validate_parameters(cls, params: ManufacturingParameters) -> Dict[str, Any]:
        """
        Validate manufacturing parameters and return validation results.
        
        Args:
            params: Manufacturing parameters to validate
            
        Returns:
            Validation results with warnings and errors
        """
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "missing_parameters": []
        }
        
        try:
            # Check required parameters
            required_params = ['quantity', 'base_material', 'pcb_thickness_mm']
            
            for param in required_params:
                if not hasattr(params, param) or getattr(params, param) is None:
                    validation_result["missing_parameters"].append(param)
                    validation_result["warnings"].append(f"Missing parameter: {param}")
            
            # Check parameter ranges
            if hasattr(params, 'quantity') and params.quantity <= 0:
                validation_result["errors"].append("Quantity must be greater than 0")
                validation_result["is_valid"] = False
            
            if hasattr(params, 'pcb_thickness_mm'):
                # Use safe thickness comparison to avoid enum comparison errors
                from app.utils.enum_helpers import get_thickness_value
                thickness_value = get_thickness_value(params.pcb_thickness_mm)
                if thickness_value <= 0:
                    validation_result["errors"].append("PCB thickness must be greater than 0")
                    validation_result["is_valid"] = False
            
            # Check material-specific parameters
            if params.base_material == BaseMaterial.flex:
                flex_params = ['coverlay_thickness', 'stiffener', 'emi_shielding_film', 'cutting_method']
                for param in flex_params:
                    if not hasattr(params, param):
                        validation_result["warnings"].append(f"Flex-specific parameter missing: {param}")
            
            elif params.base_material == BaseMaterial.aluminum:
                aluminum_params = ['thermal_conductivity', 'breakdown_voltage']
                for param in aluminum_params:
                    if not hasattr(params, param):
                        validation_result["warnings"].append(f"Aluminum-specific parameter missing: {param}")
            
            logger.info(f"Parameter validation completed: {len(validation_result['warnings'])} warnings, {len(validation_result['errors'])} errors")
            
        except Exception as e:
            logger.error(f"Parameter validation failed: {e}")
            validation_result["errors"].append(f"Validation error: {e}")
            validation_result["is_valid"] = False
        
        return validation_result
