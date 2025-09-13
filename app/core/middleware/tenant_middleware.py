# app/core/middleware/tenant_middleware.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable, Optional
import logging
import uuid
from urllib.parse import urlparse

from app.core.tenant_context import (
    set_tenant_context, 
    clear_tenant_context, 
    TenantType,
    get_tenant_context
)

logger = logging.getLogger(__name__)

class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and set tenant context from requests."""
    
    def __init__(self, app, default_tenant: str = "default"):
        super().__init__(app)
        self.default_tenant = default_tenant
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and set tenant context."""
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        
        try:
            # Extract tenant information
            tenant_info = self._extract_tenant_info(request)
            
            # Set tenant context
            set_tenant_context(
                tenant_id=tenant_info["tenant_id"],
                tenant_type=tenant_info["tenant_type"],
                user_id=tenant_info.get("user_id"),
                request_id=request_id,
                metadata=tenant_info.get("metadata", {})
            )
            
            # Add request ID to request state for error handling
            request.state.request_id = request_id
            
            # Process request
            response = await call_next(request)
            
            # Add tenant info to response headers for debugging
            response.headers["X-Tenant-ID"] = tenant_info["tenant_id"]
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            logger.error(f"Tenant middleware error: {e}")
            # Clear context on error
            clear_tenant_context()
            raise HTTPException(status_code=500, detail="Internal server error")
        
        finally:
            # Always clear context after request
            clear_tenant_context()
    
    def _extract_tenant_info(self, request: Request) -> dict:
        """Extract tenant information from request."""
        tenant_id = self.default_tenant
        tenant_type = TenantType.INDIVIDUAL
        user_id = None
        metadata = {}
        
        # 1. Check X-Tenant-ID header (highest priority)
        if tenant_header := request.headers.get("X-Tenant-ID"):
            tenant_id = tenant_header
            tenant_type = TenantType.ENTERPRISE  # Assume enterprise if explicitly set
        
        # 2. Check subdomain
        elif subdomain := self._extract_subdomain(request):
            tenant_id = subdomain
            tenant_type = TenantType.ENTERPRISE
        
        # 3. Check JWT token for tenant info
        elif jwt_tenant := self._extract_tenant_from_jwt(request):
            tenant_id = jwt_tenant["tenant_id"]
            tenant_type = jwt_tenant.get("tenant_type", TenantType.INDIVIDUAL)
            user_id = jwt_tenant.get("user_id")
        
        # 4. Check query parameter (for testing)
        elif query_tenant := request.query_params.get("tenant"):
            tenant_id = query_tenant
            tenant_type = TenantType.INDIVIDUAL
        
        # Extract user ID from JWT if available
        if not user_id:
            user_id = self._extract_user_from_jwt(request)
        
        # Add request metadata
        metadata.update({
            "user_agent": request.headers.get("User-Agent", ""),
            "ip_address": self._get_client_ip(request),
            "path": str(request.url.path),
            "method": request.method
        })
        
        return {
            "tenant_id": tenant_id,
            "tenant_type": tenant_type,
            "user_id": user_id,
            "metadata": metadata
        }
    
    def _extract_subdomain(self, request: Request) -> Optional[str]:
        """Extract tenant from subdomain."""
        try:
            host = request.headers.get("Host", "")
            if not host:
                return None
            
            # Remove port if present
            host = host.split(":")[0]
            
            # Check for subdomain pattern: tenant.domain.com
            parts = host.split(".")
            if len(parts) >= 3:
                subdomain = parts[0]
                # Skip common subdomains
                if subdomain not in ["www", "api", "app", "admin"]:
                    return subdomain
            
            return None
        except Exception:
            return None
    
    def _extract_tenant_from_jwt(self, request: Request) -> Optional[dict]:
        """Extract tenant information from JWT token."""
        try:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return None
            
            # TODO: Implement JWT parsing when auth is ready
            # For now, return None
            return None
        except Exception:
            return None
    
    def _extract_user_from_jwt(self, request: Request) -> Optional[str]:
        """Extract user ID from JWT token."""
        try:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return None
            
            # TODO: Implement JWT parsing when auth is ready
            # For now, return None
            return None
        except Exception:
            return None
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return request.client.host if request.client else "unknown"

class TenantAwareRepository:
    """Base repository class with tenant isolation."""
    
    def __init__(self, db):
        self.db = db
    
    def _add_tenant_filter(self, query: str, params: dict) -> tuple:
        """Add tenant filter to query."""
        tenant_id = get_tenant_context()
        if not tenant_id:
            raise ValueError("No tenant context available")
        
        # Add tenant_id to WHERE clause
        if "WHERE" in query.upper():
            query = query.replace("WHERE", f"WHERE tenant_id = :tenant_id AND")
        else:
            query += " WHERE tenant_id = :tenant_id"
        
        params["tenant_id"] = tenant_id.tenant_id
        return query, params
    
    async def get_tenant_quotes(self) -> list:
        """Get quotes for current tenant."""
        query = "SELECT * FROM quotes ORDER BY created_at DESC"
        params = {}
        query, params = self._add_tenant_filter(query, params)
        
        # TODO: Implement actual database query
        return []
    
    async def get_tenant_orders(self) -> list:
        """Get orders for current tenant."""
        query = "SELECT * FROM orders ORDER BY created_at DESC"
        params = {}
        query, params = self._add_tenant_filter(query, params)
        
        # TODO: Implement actual database query
        return []
