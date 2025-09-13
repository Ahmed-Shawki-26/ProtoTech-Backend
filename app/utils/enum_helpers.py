# Backend/app/utils/enum_helpers.py

from typing import Union
from app.schemas.pcb import PCBThickness
import logging

logger = logging.getLogger(__name__)

def get_thickness_value(thickness: Union[PCBThickness, float, str]) -> float:
    """
    Safely convert any thickness format to float for comparisons.
    
    Args:
        thickness: Thickness as PCBThickness enum, float, or string
        
    Returns:
        float: The thickness value in mm
    """
    try:
        if isinstance(thickness, PCBThickness):
            # Extract numeric value from enum (e.g., "1.6mm" -> 1.6)
            thickness_str = thickness.value
            if thickness_str.endswith('mm'):
                return float(thickness_str[:-2])  # Remove 'mm' suffix
            else:
                return float(thickness_str)
        elif isinstance(thickness, str):
            # Handle "1.6mm" or "1.6" format
            thickness_str = thickness.replace('mm', '').strip()
            return float(thickness_str)
        else:
            return float(thickness)
    except (ValueError, AttributeError) as e:
        logger.warning(f"Failed to convert thickness {thickness} to float: {e}")
        # Default to 1.6mm if conversion fails
        return 1.6

def safe_thickness_compare(thickness: Union[PCBThickness, float, str], value: float, operation: str = '<=') -> bool:
    """
    Safely compare thickness with a float value.
    
    Args:
        thickness: Thickness as PCBThickness enum, float, or string
        value: Float value to compare against
        operation: Comparison operation ('<=', '>=', '<', '>', '==')
        
    Returns:
        bool: Result of the comparison
    """
    try:
        thickness_value = get_thickness_value(thickness)
        
        if operation == '<=':
            return thickness_value <= value
        elif operation == '>=':
            return thickness_value >= value
        elif operation == '<':
            return thickness_value < value
        elif operation == '>':
            return thickness_value > value
        elif operation == '==':
            return thickness_value == value
        else:
            logger.warning(f"Unknown comparison operation: {operation}")
            return True  # Default safe value
    except Exception as e:
        logger.error(f"Error in thickness comparison: {e}")
        return True  # Default safe value

def get_thickness_multiplier(thickness: Union[PCBThickness, float, str], thickness_multipliers: dict) -> float:
    """
    Get thickness multiplier from a dictionary using safe thickness conversion.
    
    Args:
        thickness: Thickness as PCBThickness enum, float, or string
        thickness_multipliers: Dictionary mapping thickness values to multipliers
        
    Returns:
        float: The thickness multiplier
    """
    try:
        thickness_value = get_thickness_value(thickness)
        return thickness_multipliers.get(thickness_value, 1.0)
    except Exception as e:
        logger.error(f"Error getting thickness multiplier: {e}")
        return 1.0  # Default multiplier
