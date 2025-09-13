# app/core/error_handlers.py

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging
import traceback
from typing import Union

from .exceptions import (
    ProtoTechError, 
    PricingError, 
    ParameterValidationError,
    FileProcessingError,
    DimensionValidationError,
    ErrorCode
)

logger = logging.getLogger(__name__)

def setup_error_handlers(app: FastAPI):
    """Set up global error handlers for the FastAPI application."""
    
    @app.exception_handler(ProtoTechError)
    async def prototech_error_handler(request: Request, exc: ProtoTechError):
        """Handle custom ProtoTech errors."""
        
        # Determine appropriate status code based on error type
        status_code_map = {
            ErrorCode.INVALID_PARAMETERS: 400,
            ErrorCode.MISSING_REQUIRED_PARAMETER: 400,
            ErrorCode.PARAMETER_OUT_OF_RANGE: 400,
            ErrorCode.UNSUPPORTED_MATERIAL: 400,
            ErrorCode.PRICING_CALCULATION_FAILED: 400,
            ErrorCode.DIMENSION_OUT_OF_RANGE: 400,
            ErrorCode.MATERIAL_NOT_SUPPORTED: 400,
            ErrorCode.QUANTITY_TOO_LOW: 400,
            ErrorCode.INVALID_FILE_TYPE: 400,
            ErrorCode.FILE_TOO_LARGE: 413,
            ErrorCode.GERBER_PARSING_FAILED: 422,
            ErrorCode.NO_PCB_LAYERS_FOUND: 422,
            ErrorCode.INTERNAL_SERVER_ERROR: 500,
            ErrorCode.SERVICE_UNAVAILABLE: 503,
            ErrorCode.RATE_LIMIT_EXCEEDED: 429,
            ErrorCode.CACHE_UNAVAILABLE: 503,
            ErrorCode.CACHE_OPERATION_FAILED: 503,
        }
        
        status_code = status_code_map.get(exc.code, 400)
        
        # Log the error with request context
        logger.error(
            f"ProtoTech Error: {exc.code.value}",
            extra={
                "error_code": exc.code.value,
                "user_message": exc.user_message,
                "technical_details": exc.technical_details,
                "context": exc.context,
                "suggested_action": exc.suggested_action,
                "request_url": str(request.url),
                "request_method": request.method,
                "client_ip": request.client.host if request.client else None
            }
        )
        
        return JSONResponse(
            status_code=status_code,
            content=exc.to_response()
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors with better formatting."""
        
        # Extract validation errors
        errors = []
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field_path,
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input")
            })
        
        logger.warning(
            "Validation error",
            extra={
                "validation_errors": errors,
                "request_url": str(request.url),
                "request_method": request.method
            }
        )
        
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": errors
                }
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle standard HTTP exceptions with consistent format."""
        
        # Check if this is already a ProtoTech error format
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail
            )
        
        logger.warning(
            f"HTTP Exception: {exc.status_code}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "request_url": str(request.url),
                "request_method": request.method
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "status_code": exc.status_code
                }
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle ValueError exceptions with better context."""
        
        logger.error(
            f"ValueError: {str(exc)}",
            extra={
                "error_message": str(exc),
                "request_url": str(request.url),
                "request_method": request.method,
                "traceback": traceback.format_exc()
            }
        )
        
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALUE_ERROR",
                    "message": "Invalid value provided",
                    "details": str(exc)
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions with proper logging."""
        
        # Log the full traceback for debugging
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
            extra={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "request_url": str(request.url),
                "request_method": request.method,
                "traceback": traceback.format_exc()
            }
        )
        
        # Don't expose internal details in production
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred. Please try again later.",
                    "details": "Contact support if the problem persists."
                }
            }
        )

# Utility function to create consistent error responses
def create_error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: dict = None
) -> JSONResponse:
    """Create a consistent error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {}
            }
        }
    )

# Middleware for request ID tracking
async def add_request_id_middleware(request: Request, call_next):
    """Add request ID for better error tracking."""
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
