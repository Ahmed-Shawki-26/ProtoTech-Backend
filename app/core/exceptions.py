# app/core/exceptions.py

from enum import Enum
from typing import Optional, Dict, Any, List
import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class ErrorCode(Enum):
    """Standardized error codes for the application."""
    
    # Parameter validation errors
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    MISSING_REQUIRED_PARAMETER = "MISSING_REQUIRED_PARAMETER"
    PARAMETER_OUT_OF_RANGE = "PARAMETER_OUT_OF_RANGE"
    UNSUPPORTED_MATERIAL = "UNSUPPORTED_MATERIAL"
    
    # Pricing calculation errors
    PRICING_CALCULATION_FAILED = "PRICING_CALCULATION_FAILED"
    DIMENSION_OUT_OF_RANGE = "DIMENSION_OUT_OF_RANGE"
    MATERIAL_NOT_SUPPORTED = "MATERIAL_NOT_SUPPORTED"
    QUANTITY_TOO_LOW = "QUANTITY_TOO_LOW"
    
    # File processing errors
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    GERBER_PARSING_FAILED = "GERBER_PARSING_FAILED"
    NO_PCB_LAYERS_FOUND = "NO_PCB_LAYERS_FOUND"
    
    # System errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Cache errors
    CACHE_UNAVAILABLE = "CACHE_UNAVAILABLE"
    CACHE_OPERATION_FAILED = "CACHE_OPERATION_FAILED"

class ProtoTechError(Exception):
    """Base exception for all ProtoTech application errors."""
    
    def __init__(
        self,
        code: ErrorCode,
        user_message: str,
        technical_details: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        suggested_action: Optional[str] = None
    ):
        self.code = code
        self.user_message = user_message
        self.technical_details = technical_details
        self.context = context or {}
        self.suggested_action = suggested_action
        
        # Log the error
        logger.error(
            f"ProtoTech Error: {code.value}",
            extra={
                "error_code": code.value,
                "user_message": user_message,
                "technical_details": technical_details,
                "context": self.context,
                "suggested_action": suggested_action
            }
        )
        
        super().__init__(self.user_message)
    
    def to_response(self) -> Dict[str, Any]:
        """Convert to API response format."""
        response = {
            "error": {
                "code": self.code.value,
                "message": self.user_message,
                "context": self.context
            }
        }
        
        if self.suggested_action:
            response["error"]["suggested_action"] = self.suggested_action
        
        return response
    
    def to_http_exception(self, status_code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(
            status_code=status_code,
            detail=self.to_response()
        )

class PricingError(ProtoTechError):
    """Specific error for pricing calculation issues."""
    
    def __init__(
        self,
        code: ErrorCode,
        user_message: str,
        technical_details: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        suggested_action: Optional[str] = None
    ):
        super().__init__(code, user_message, technical_details, context, suggested_action)

class ParameterValidationError(ProtoTechError):
    """Specific error for parameter validation issues."""
    
    def __init__(
        self,
        parameter_name: str,
        parameter_value: Any,
        expected_format: str,
        technical_details: Optional[str] = None
    ):
        user_message = f"Invalid value for '{parameter_name}': {parameter_value}. Expected: {expected_format}"
        suggested_action = f"Please provide a valid value for {parameter_name}"
        
        super().__init__(
            code=ErrorCode.INVALID_PARAMETERS,
            user_message=user_message,
            technical_details=technical_details,
            context={
                "parameter_name": parameter_name,
                "parameter_value": str(parameter_value),
                "expected_format": expected_format
            },
            suggested_action=suggested_action
        )

class FileProcessingError(ProtoTechError):
    """Specific error for file processing issues."""
    
    def __init__(
        self,
        code: ErrorCode,
        user_message: str,
        filename: Optional[str] = None,
        technical_details: Optional[str] = None
    ):
        context = {}
        if filename:
            context["filename"] = filename
            
        super().__init__(code, user_message, technical_details, context)

class AuthenticationError(Exception):
    """Exception raised for authentication-related errors."""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class UserNotFoundError(Exception):
    """Exception raised when a user is not found."""
    
    def __init__(self, message: str = "User not found"):
        self.message = message
        super().__init__(self.message)

class InvalidPasswordError(Exception):
    """Exception raised when password is invalid."""
    
    def __init__(self, message: str = "Invalid password"):
        self.message = message
        super().__init__(self.message)

class PasswordMismatchError(Exception):
    """Exception raised when passwords don't match."""
    
    def __init__(self, message: str = "Passwords do not match"):
        self.message = message
        super().__init__(self.message)

class DimensionValidationError(ProtoTechError):
    """Specific error for dimension validation issues."""
    
    def __init__(
        self,
        dimension_type: str,
        provided_value: float,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        unit: str = "mm"
    ):
        if min_value is not None and max_value is not None:
            user_message = f"{dimension_type} must be between {min_value}{unit} and {max_value}{unit}. Provided: {provided_value}{unit}"
            suggested_action = f"Please provide a {dimension_type} between {min_value}{unit} and {max_value}{unit}"
        elif min_value is not None:
            user_message = f"{dimension_type} must be at least {min_value}{unit}. Provided: {provided_value}{unit}"
            suggested_action = f"Please provide a {dimension_type} of at least {min_value}{unit}"
        else:
            user_message = f"{dimension_type} must be at most {max_value}{unit}. Provided: {provided_value}{unit}"
            suggested_action = f"Please provide a {dimension_type} of at most {max_value}{unit}"
        
        super().__init__(
            code=ErrorCode.DIMENSION_OUT_OF_RANGE,
            user_message=user_message,
            context={
                "dimension_type": dimension_type,
                "provided_value": provided_value,
                "min_value": min_value,
                "max_value": max_value,
                "unit": unit
            },
            suggested_action=suggested_action
        )

# Convenience functions for common errors
def raise_invalid_parameter(parameter_name: str, value: Any, expected_format: str):
    """Raise a parameter validation error."""
    raise ParameterValidationError(parameter_name, value, expected_format)

def raise_dimension_error(dimension_type: str, value: float, min_val: float = None, max_val: float = None):
    """Raise a dimension validation error."""
    raise DimensionValidationError(dimension_type, value, min_val, max_val)

def raise_pricing_error(message: str, technical_details: str = None, context: Dict[str, Any] = None):
    """Raise a pricing calculation error."""
    raise PricingError(
        code=ErrorCode.PRICING_CALCULATION_FAILED,
        user_message=message,
        technical_details=technical_details,
        context=context
    )

def raise_material_error(material: str, supported_materials: List[str]):
    """Raise an unsupported material error."""
    raise ProtoTechError(
        code=ErrorCode.UNSUPPORTED_MATERIAL,
        user_message=f"Material '{material}' is not supported",
        technical_details=f"Supported materials: {', '.join(supported_materials)}",
        context={
            "provided_material": material,
            "supported_materials": supported_materials
        },
        suggested_action=f"Please choose from: {', '.join(supported_materials)}"
    )

def raise_file_error(filename: str, error_type: str, technical_details: str = None):
    """Raise a file processing error."""
    code_map = {
        "invalid_type": ErrorCode.INVALID_FILE_TYPE,
        "too_large": ErrorCode.FILE_TOO_LARGE,
        "parsing_failed": ErrorCode.GERBER_PARSING_FAILED,
        "no_layers": ErrorCode.NO_PCB_LAYERS_FOUND
    }
    
    message_map = {
        "invalid_type": f"File '{filename}' is not a supported type. Please upload a ZIP or RAR file.",
        "too_large": f"File '{filename}' is too large. Maximum size is 50MB.",
        "parsing_failed": f"Failed to parse Gerber files in '{filename}'. Please check the file format.",
        "no_layers": f"No PCB layers found in '{filename}'. Please ensure the file contains valid Gerber layers."
    }
    
    action_map = {
        "invalid_type": "Please upload a ZIP or RAR file containing Gerber layers.",
        "too_large": "Please compress the file or split it into smaller parts.",
        "parsing_failed": "Please verify the Gerber file format and try again.",
        "no_layers": "Please ensure the file contains valid PCB layers (copper, solder mask, silkscreen)."
    }
    
    raise FileProcessingError(
        code=code_map.get(error_type, ErrorCode.INTERNAL_SERVER_ERROR),
        user_message=message_map.get(error_type, f"Error processing file '{filename}'"),
        filename=filename,
        technical_details=technical_details
    )