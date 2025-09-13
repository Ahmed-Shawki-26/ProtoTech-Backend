# app/services/parameter_normalizer.py

from typing import Union, Dict, Any, Optional
from enum import Enum
import logging
from app.schemas.pcb import (
    BaseMaterial, 
    MinViaHole, 
    BoardOutlineTolerance,
    ManufacturingParameters,
    PCBThickness
)

logger = logging.getLogger(__name__)

class ParameterNormalizer:
    """
    Handles all frontend→backend parameter conversions and normalization.
    This is the single source of truth for parameter format conversion.
    """
    
    # Frontend to backend mapping for materials
    MATERIAL_MAPPING = {
        "FR-4": BaseMaterial.fr4,
        "Flex": BaseMaterial.flex,
        "Aluminum": BaseMaterial.aluminum,
    }
    
    # Via hole size mapping (frontend format → backend enum)
    VIA_HOLE_MAPPING = {
        "0.3": MinViaHole.h_30_mm,
        "0.3mm": MinViaHole.h_30_mm,
        "0.25": MinViaHole.h_25_mm,
        "0.25mm": MinViaHole.h_25_mm,
        "0.2": MinViaHole.h_20_mm,
        "0.2mm": MinViaHole.h_20_mm,
        "0.15": MinViaHole.h_15_mm,
        "0.15mm": MinViaHole.h_15_mm,
    }
    
    # Tolerance mapping
    TOLERANCE_MAPPING = {
        "0.2mm": BoardOutlineTolerance.regular,
        "±0.2mm": BoardOutlineTolerance.regular,
        "±0.2mm (Regular)": BoardOutlineTolerance.regular,
        "0.1mm": BoardOutlineTolerance.precision,
        "±0.1mm": BoardOutlineTolerance.precision,
        "±0.1mm (Precision)": BoardOutlineTolerance.precision,
    }
    
    @staticmethod
    def normalize_via_hole(value: Union[str, float, MinViaHole, None]) -> MinViaHole:
        """
        Convert any via hole format to MinViaHole enum.
        
        Args:
            value: Can be string ("0.3", "0.3mm"), float (0.3), or MinViaHole enum
            
        Returns:
            MinViaHole enum value
            
        Raises:
            ValueError: If value cannot be normalized
        """
        if value is None:
            return MinViaHole.h_30_mm  # Default value
            
        if isinstance(value, MinViaHole):
            return value
            
        if isinstance(value, str):
            # Clean the string (remove "mm", whitespace)
            clean_value = value.replace('mm', '').strip()
            if clean_value in ParameterNormalizer.VIA_HOLE_MAPPING:
                return ParameterNormalizer.VIA_HOLE_MAPPING[clean_value]
            # Try direct mapping
            if value in ParameterNormalizer.VIA_HOLE_MAPPING:
                return ParameterNormalizer.VIA_HOLE_MAPPING[value]
                
        if isinstance(value, (int, float)):
            str_value = str(value)
            if str_value in ParameterNormalizer.VIA_HOLE_MAPPING:
                return ParameterNormalizer.VIA_HOLE_MAPPING[str_value]
        
        # If we get here, try to find the closest match
        if isinstance(value, (int, float)):
            if value >= 0.3:
                return MinViaHole.h_30_mm
            elif value >= 0.25:
                return MinViaHole.h_25_mm
            elif value >= 0.2:
                return MinViaHole.h_20_mm
            else:
                return MinViaHole.h_15_mm
        
        raise ValueError(f"Cannot normalize via hole value: {value}")
    
    @staticmethod
    def normalize_material(value: Union[str, BaseMaterial, None]) -> BaseMaterial:
        """
        Convert material string to BaseMaterial enum.
        
        Args:
            value: Material string or BaseMaterial enum
            
        Returns:
            BaseMaterial enum value
            
        Raises:
            ValueError: If material is not supported
        """
        if value is None:
            return BaseMaterial.fr4  # Default value
            
        if isinstance(value, BaseMaterial):
            return value
            
        if isinstance(value, str):
            if value in ParameterNormalizer.MATERIAL_MAPPING:
                return ParameterNormalizer.MATERIAL_MAPPING[value]
        
        raise ValueError(f"Unsupported material: {value}")
    
    @staticmethod
    def normalize_tolerance(value: Union[str, BoardOutlineTolerance, None]) -> BoardOutlineTolerance:
        """
        Convert tolerance string to BoardOutlineTolerance enum.
        
        Args:
            value: Tolerance string or BoardOutlineTolerance enum
            
        Returns:
            BoardOutlineTolerance enum value
        """
        if value is None:
            return BoardOutlineTolerance.regular  # Default value
            
        if isinstance(value, BoardOutlineTolerance):
            return value
            
        if isinstance(value, str):
            if value in ParameterNormalizer.TOLERANCE_MAPPING:
                return ParameterNormalizer.TOLERANCE_MAPPING[value]
        
        # Default to regular tolerance
        logger.warning(f"Unknown tolerance value: {value}, using default")
        return BoardOutlineTolerance.regular
    
    @staticmethod
    def normalize_thickness(value: Union[str, float, None]) -> PCBThickness:
        """
        Convert thickness to PCBThickness enum value.
        
        Args:
            value: Thickness as string ("1.6mm", "1.6") or float
            
        Returns:
            PCBThickness enum value
        """
        if value is None:
            return PCBThickness.t_1_6_mm  # Default thickness
            
        if isinstance(value, (int, float)):
            # Convert float to string with mm suffix
            thickness_str = f"{float(value)}mm"
            try:
                return PCBThickness(thickness_str)
            except ValueError:
                logger.warning(f"Cannot map thickness: {thickness_str}, using default 1.6mm")
                return PCBThickness.t_1_6_mm
            
        if isinstance(value, str):
            # Ensure it has mm suffix
            if not value.endswith('mm'):
                thickness_str = f"{value}mm"
            else:
                thickness_str = value
                
            try:
                return PCBThickness(thickness_str)
            except ValueError:
                logger.warning(f"Cannot map thickness: {thickness_str}, using default 1.6mm")
                return PCBThickness.t_1_6_mm
        
        raise ValueError(f"Cannot normalize thickness value: {value}")
    
    @staticmethod
    def normalize_quantity(value: Union[str, int, None]) -> int:
        """
        Convert quantity to integer.
        
        Args:
            value: Quantity as string or integer
            
        Returns:
            Quantity as integer
        """
        if value is None:
            return 5  # Default quantity
            
        if isinstance(value, int):
            return value
            
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                logger.warning(f"Cannot parse quantity: {value}, using default 5")
                return 5
        
        raise ValueError(f"Cannot normalize quantity value: {value}")
    
    @classmethod
    def normalize_parameters(cls, raw_params: Dict[str, Any]) -> ManufacturingParameters:
        """
        Normalize all parameters from frontend format to backend format.
        
        Args:
            raw_params: Raw parameters from frontend
            
        Returns:
            Normalized ManufacturingParameters object
        """
        try:
            # Extract and normalize core parameters
            normalized = {
                'quantity': cls.normalize_quantity(raw_params.get('quantity')),
                'base_material': cls.normalize_material(raw_params.get('base_material')),
                'min_via_hole_size_dia': cls.normalize_via_hole(raw_params.get('min_via_hole_size_dia')),
                'board_outline_tolerance': cls.normalize_tolerance(raw_params.get('board_outline_tolerance')),
            }
            
            # Handle optional parameters with defaults
            if 'different_designs' in raw_params:
                normalized['different_designs'] = cls.normalize_quantity(raw_params['different_designs'])
            
            if 'delivery_format' in raw_params:
                normalized['delivery_format'] = raw_params['delivery_format']
            
            # Handle thickness
            if 'thickness' in raw_params:
                normalized['pcb_thickness_mm'] = cls.normalize_thickness(raw_params['thickness'])
            elif 'pcb_thickness_mm' in raw_params:
                normalized['pcb_thickness_mm'] = cls.normalize_thickness(raw_params['pcb_thickness_mm'])
            
            # Handle other string parameters (pass through)
            string_params = [
                'layers', 'product_type', 'pcb_color', 'silkscreen', 
                'surface_finish', 'outer_copper_weight', 'via_covering',
                'pcb_remark', 'confirm_production_file', 'electrical_test'
            ]
            
            for param in string_params:
                if param in raw_params:
                    normalized[param] = raw_params[param]
            
            # Handle legacy boolean parameters (convert to strings)
            boolean_to_string_params = ['confirm_production_file', 'electrical_test']
            for param in boolean_to_string_params:
                if param in raw_params:
                    value = raw_params[param]
                    if isinstance(value, bool):
                        # Convert boolean to string
                        if param == 'confirm_production_file':
                            normalized[param] = "Yes" if value else "No"
                        elif param == 'electrical_test':
                            normalized[param] = "optical manual inspection" if value else "optical manual inspection"
                    elif isinstance(value, str):
                        normalized[param] = value
            
            # Handle silkscreen normalization
            if 'silkscreen' in raw_params:
                silkscreen_value = raw_params['silkscreen']
                if isinstance(silkscreen_value, str):
                    # Normalize silkscreen color
                    silkscreen_str = silkscreen_value.strip().lower()
                    if silkscreen_str in ['white', 'black']:
                        normalized['silkscreen'] = silkscreen_str.capitalize()
                    else:
                        # Default to white if invalid
                        normalized['silkscreen'] = 'White'
                else:
                    normalized['silkscreen'] = 'White'
            
            # Handle numeric parameters
            if 'width_mm' in raw_params:
                normalized['width_mm'] = float(raw_params['width_mm'])
            if 'height_mm' in raw_params:
                normalized['height_mm'] = float(raw_params['height_mm'])
            
            logger.info(f"Normalized parameters: {list(normalized.keys())}")
            return ManufacturingParameters(**normalized)
            
        except Exception as e:
            logger.error(f"Failed to normalize parameters: {e}")
            logger.error(f"Raw parameters: {raw_params}")
            raise ValueError(f"Parameter normalization failed: {e}")
    
    @classmethod
    def validate_and_normalize(cls, raw_params: Dict[str, Any]) -> tuple[ManufacturingParameters, list[str]]:
        """
        Validate and normalize parameters, returning warnings for any issues.
        
        Args:
            raw_params: Raw parameters from frontend
            
        Returns:
            Tuple of (normalized_parameters, warnings_list)
        """
        warnings = []
        
        try:
            # Check for common issues
            if 'min_via_hole_size_dia' in raw_params:
                original = raw_params['min_via_hole_size_dia']
                if isinstance(original, str) and 'mm' in original:
                    warnings.append(f"Via hole format '{original}' should be '{original.replace('mm', '')}'")
            
            if 'thickness' in raw_params:
                original = raw_params['thickness']
                if isinstance(original, str) and not original.endswith('mm'):
                    warnings.append(f"Thickness format '{original}' should include 'mm' suffix")
            
            # Normalize parameters
            normalized = cls.normalize_parameters(raw_params)
            
            return normalized, warnings
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise

# Convenience function for easy import
def normalize_parameters(raw_params: Dict[str, Any]) -> ManufacturingParameters:
    """Convenience function for parameter normalization."""
    return ParameterNormalizer.normalize_parameters(raw_params)
