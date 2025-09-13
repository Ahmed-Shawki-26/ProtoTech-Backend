# app/services/parameter_validator.py

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.schemas.pcb import ManufacturingParameters, BoardDimensions
from app.core.exceptions import (
    ParameterValidationError, 
    DimensionValidationError, 
    raise_dimension_error,
    ErrorCode
)

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of parameter validation."""
    is_valid: bool
    warnings: List[str]
    errors: List[str]
    normalized_params: Optional[ManufacturingParameters] = None

class ParameterValidator:
    """
    Validates and normalizes all input parameters.
    Ensures data integrity before pricing calculations.
    """
    
    # Validation limits
    MAX_BOARD_WIDTH_MM = 500.0
    MAX_BOARD_HEIGHT_MM = 500.0
    MAX_BOARD_AREA_CM2 = 2500.0  # 25 cm × 10 cm
    MIN_BOARD_WIDTH_MM = 5.0
    MIN_BOARD_HEIGHT_MM = 5.0
    MIN_BOARD_AREA_CM2 = 0.25  # 0.5 cm × 0.5 cm
    
    MAX_QUANTITY = 10000
    MIN_QUANTITY = 1
    
    # Supported materials
    SUPPORTED_MATERIALS = [
        "FR-4", "Flex", "Aluminum", "Copper Core", "Rogers", "PTFE"
    ]
    
    # Supported thicknesses (updated with new specifications)
    SUPPORTED_THICKNESSES = ["0.6", "0.8", "1.0", "1.2", "1.6", "2.0"]
    
    # Supported colors (lowercase for consistency)
    SUPPORTED_COLORS = ["green", "blue", "red", "black", "white", "yellow"]
    
    # Material-specific specifications
    MATERIAL_SPECIFICATIONS = {
        "FR-4": {
            "layers": [1, 2, 4, 6, 8],
            "thicknesses": ["0.6", "0.8", "1.0", "1.2", "1.6", "2.0"],
            "colors": ["green", "blue", "red", "black", "white", "yellow"],
            "silkscreen": ["white", "black"],
            "surface_finishes": ["HASL", "ENIG", "immersion tin"],
            "copper_weights": ["1", "2", "3"]
        },
        "Flex": {
            "layers": [1, 2],
            "thicknesses": ["0.12"],
            "colors": ["yellow"],  # Coverlay color
            "silkscreen": ["white"],
            "surface_finishes": ["immersion tin"],
            "copper_weights": ["1/3 oz"]
        },
        "Aluminum": {
            "layers": [1],
            "thicknesses": ["0.6", "0.8", "1.0", "1.2", "1.6", "2.0"],
            "colors": ["green", "blue", "red", "black", "white", "yellow"],
            "silkscreen": ["white", "black"],
            "surface_finishes": ["HASL", "ENIG", "immersion tin"],
            "copper_weights": ["1"]
        }
    }
    
    def __init__(self):
        logger.info("ParameterValidator initialized")
    
    def normalize(self, params: ManufacturingParameters) -> ManufacturingParameters:
        """
        Normalize parameters to ensure consistency.
        
        Args:
            params: Raw manufacturing parameters
            
        Returns:
            Normalized ManufacturingParameters
        """
        try:
            # Create a copy to avoid modifying the original
            normalized_data = params.model_dump()
            
            # Normalize thickness
            if 'pcb_thickness_mm' in normalized_data:
                thickness = normalized_data['pcb_thickness_mm']
                if isinstance(thickness, str) and not thickness.endswith('mm'):
                    normalized_data['pcb_thickness_mm'] = f"{thickness}mm"
            
            # Normalize quantity to integer
            if 'quantity' in normalized_data:
                normalized_data['quantity'] = int(normalized_data['quantity'])
            
            # Normalize string fields that were previously boolean
            string_fields = ['confirm_production_file', 'electrical_test']
            for field in string_fields:
                if field in normalized_data:
                    value = normalized_data[field]
                    if isinstance(value, bool):
                        # Convert boolean to string
                        if field == 'confirm_production_file':
                            normalized_data[field] = "Yes" if value else "No"
                        elif field == 'electrical_test':
                            normalized_data[field] = "optical manual inspection"  # Default value
                    elif isinstance(value, str):
                        # Keep as string
                        normalized_data[field] = value
            
            # Create new instance with normalized data
            normalized_params = ManufacturingParameters(**normalized_data)
            
            logger.debug("Parameters normalized successfully")
            return normalized_params
            
        except Exception as e:
            logger.error(f"Parameter normalization failed: {e}")
            raise ParameterValidationError(
                "parameters", 
                str(e), 
                "valid manufacturing parameters"
            )
    
    def validate_parameters(self, params: ManufacturingParameters) -> ValidationResult:
        """
        Validate manufacturing parameters.
        
        Args:
            params: Manufacturing parameters to validate
            
        Returns:
            ValidationResult with validation status and messages
        """
        warnings = []
        errors = []
        
        try:
            # Validate quantity
            if not (self.MIN_QUANTITY <= params.quantity <= self.MAX_QUANTITY):
                errors.append(f"Quantity must be between {self.MIN_QUANTITY} and {self.MAX_QUANTITY}")
            
            # Validate material
            material = params.base_material.value
            if material not in self.SUPPORTED_MATERIALS:
                errors.append(f"Unsupported material: {material}")
            else:
                # Material-specific validation
                material_specs = self.MATERIAL_SPECIFICATIONS.get(material, {})
                
                # Validate thickness
                thickness = getattr(params, 'pcb_thickness_mm', '1.6')
                if isinstance(thickness, str):
                    thickness = thickness.replace('mm', '')
                if material_specs.get('thicknesses') and str(thickness) not in material_specs['thicknesses']:
                    errors.append(f"Unsupported thickness for {material}: {thickness}mm")
                
                # Validate color
                color = getattr(params, 'pcb_color', 'green')
                if isinstance(color, str):
                    color = color.lower()
                if material_specs.get('colors') and color not in material_specs['colors']:
                    errors.append(f"Unsupported color for {material}: {color}")
                
                # Validate copper weight
                copper_weight = getattr(params, 'outer_copper_weight', '1 oz')
                if material_specs.get('copper_weights') and copper_weight not in material_specs['copper_weights']:
                    errors.append(f"Unsupported copper weight for {material}: {copper_weight}")
                
                # Validate surface finish
                surface_finish = getattr(params, 'surface_finish', 'HASL')
                if isinstance(surface_finish, str):
                    surface_finish = surface_finish.lower()
                if material_specs.get('surface_finishes') and surface_finish not in material_specs['surface_finishes']:
                    errors.append(f"Unsupported surface finish for {material}: {surface_finish}")
                
                # Validate silkscreen color
                silkscreen = getattr(params, 'silkscreen', 'white')
                if isinstance(silkscreen, str):
                    silkscreen = silkscreen.lower()
                if material_specs.get('silkscreen') and silkscreen not in material_specs['silkscreen']:
                    errors.append(f"Unsupported silkscreen color for {material}: {silkscreen}")
                
                # Special validation for white/black PCBs
                if color in ['white', 'black']:
                    if color == 'white' and silkscreen != 'black':
                        warnings.append("White PCBs should use black silkscreen for better contrast")
                    elif color == 'black' and silkscreen != 'white':
                        warnings.append("Black PCBs should use white silkscreen for better contrast")
            
            # Validate via hole size
            via_hole = float(params.min_via_hole_size_dia.value)
            if via_hole < 0.1 or via_hole > 0.5:
                warnings.append(f"Extreme via hole size: {via_hole}mm")
            
            # Check for potential issues
            if params.quantity == 1:
                warnings.append("Single quantity may have higher per-unit cost")
            
            if getattr(params, 'base_material', None) and params.base_material.value in ['Rogers', 'PTFE']:
                warnings.append("Premium materials may have longer lead times")
            
            is_valid = len(errors) == 0
            
            logger.debug(f"Parameter validation completed: valid={is_valid}, "
                        f"warnings={len(warnings)}, errors={len(errors)}")
            
            return ValidationResult(
                is_valid=is_valid,
                warnings=warnings,
                errors=errors,
                normalized_params=params
            )
            
        except Exception as e:
            logger.error(f"Parameter validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                warnings=[],
                errors=[f"Validation failed: {str(e)}"]
            )
    
    def validate_dimensions(self, dimensions: BoardDimensions) -> ValidationResult:
        """
        Validate board dimensions.
        
        Args:
            dimensions: Board dimensions to validate
            
        Returns:
            ValidationResult with validation status
        """
        warnings = []
        errors = []
        
        try:
            # Validate width
            if not (self.MIN_BOARD_WIDTH_MM <= dimensions.width_mm <= self.MAX_BOARD_WIDTH_MM):
                raise_dimension_error(
                    "width", 
                    dimensions.width_mm, 
                    self.MIN_BOARD_WIDTH_MM, 
                    self.MAX_BOARD_WIDTH_MM
                )
            
            # Validate height
            if not (self.MIN_BOARD_HEIGHT_MM <= dimensions.height_mm <= self.MAX_BOARD_HEIGHT_MM):
                raise_dimension_error(
                    "height", 
                    dimensions.height_mm, 
                    self.MIN_BOARD_HEIGHT_MM, 
                    self.MAX_BOARD_HEIGHT_MM
                )
            
            # Validate area
            area_cm2 = dimensions.area_m2 * 10000  # Convert m² to cm²
            if not (self.MIN_BOARD_AREA_CM2 <= area_cm2 <= self.MAX_BOARD_AREA_CM2):
                raise_dimension_error(
                    "area", 
                    area_cm2, 
                    self.MIN_BOARD_AREA_CM2, 
                    self.MAX_BOARD_AREA_CM2,
                    unit="cm²"
                )
            
            # Check for unusual aspect ratios
            aspect_ratio = dimensions.width_mm / dimensions.height_mm
            if aspect_ratio > 10.0 or aspect_ratio < 0.1:
                warnings.append(f"Unusual aspect ratio: {aspect_ratio:.2f}")
            
            # Check for very small boards
            if area_cm2 < 1.0:
                warnings.append("Very small board may have minimum pricing")
            
            # Check for very large boards
            if area_cm2 > 1000.0:
                warnings.append("Large board may have special handling requirements")
            
            logger.debug(f"Dimension validation completed: "
                        f"warnings={len(warnings)}, errors={len(errors)}")
            
            return ValidationResult(
                is_valid=True,
                warnings=warnings,
                errors=errors
            )
            
        except DimensionValidationError:
            # Re-raise dimension errors
            raise
        except Exception as e:
            logger.error(f"Dimension validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                warnings=[],
                errors=[f"Dimension validation failed: {str(e)}"]
            )
    
    def validate_parameter_combinations(
        self, 
        params: ManufacturingParameters, 
        dimensions: BoardDimensions
    ) -> ValidationResult:
        """
        Validate parameter combinations for business logic.
        
        Args:
            params: Manufacturing parameters
            dimensions: Board dimensions
            
        Returns:
            ValidationResult with combination-specific warnings
        """
        warnings = []
        errors = []
        
        try:
            # Check material vs thickness compatibility
            thickness = getattr(params, 'pcb_thickness_mm', '1.6')
            if isinstance(thickness, str):
                thickness = float(thickness.replace('mm', ''))
            else:
                thickness = float(thickness)
            
            if params.base_material.value == 'Flex' and thickness > 0.2:
                warnings.append("Flex PCBs typically use thinner substrates")
            
            if params.base_material.value == 'Aluminum' and thickness < 1.0:
                warnings.append("Aluminum PCBs typically use thicker substrates")
            
            # Check via hole vs thickness
            via_hole = float(params.min_via_hole_size_dia.value)
            if via_hole > thickness * 0.8:
                warnings.append("Via hole size is large relative to board thickness")
            
            # Check quantity vs board size
            area_cm2 = dimensions.area_m2 * 10000
            if params.quantity > 100 and area_cm2 > 100:
                warnings.append("Large quantity of large boards may require special handling")
            
            # Check color vs material
            color = getattr(params, 'pcb_color', 'Green')
            if params.base_material.value == 'Aluminum' and color == 'Green':
                warnings.append("Green color on aluminum may have limited availability")
            
            logger.debug(f"Combination validation completed: "
                        f"warnings={len(warnings)}, errors={len(errors)}")
            
            return ValidationResult(
                is_valid=True,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Combination validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                warnings=[],
                errors=[f"Combination validation failed: {str(e)}"]
            )
    
    def get_validation_summary(self, result: ValidationResult) -> Dict[str, Any]:
        """Get a summary of validation results for API responses."""
        return {
            "is_valid": result.is_valid,
            "warnings_count": len(result.warnings),
            "errors_count": len(result.errors),
            "warnings": result.warnings,
            "errors": result.errors,
            "has_warnings": len(result.warnings) > 0,
            "has_errors": len(result.errors) > 0
        }

# Global parameter validator instance
parameter_validator = ParameterValidator()
