# app/core/tenant_context.py

from contextvars import ContextVar
from typing import Optional, Dict, Any
import logging
from enum import Enum

logger = logging.getLogger(__name__)

# Thread-safe tenant context
current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)
current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)
_request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

class TenantType(Enum):
    """Types of tenants supported by the system."""
    INDIVIDUAL = "individual"
    ENTERPRISE = "enterprise"
    PARTNER = "partner"
    INTERNAL = "internal"

class TenantContext:
    """Context information for the current tenant."""
    
    def __init__(
        self,
        tenant_id: str,
        tenant_type: TenantType = TenantType.INDIVIDUAL,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.tenant_id = tenant_id
        self.tenant_type = tenant_type
        self.user_id = user_id
        self.request_id = request_id
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging."""
        return {
            "tenant_id": self.tenant_id,
            "tenant_type": self.tenant_type.value,
            "user_id": self.user_id,
            "request_id": self.request_id,
            "metadata": self.metadata
        }

def get_current_tenant() -> Optional[str]:
    """Get the current tenant ID from context."""
    return current_tenant.get()

def get_current_user() -> Optional[str]:
    """Get the current user ID from context."""
    return current_user_id.get()

def get_current_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _request_id_context.get()

def set_tenant_context(
    tenant_id: str,
    tenant_type: TenantType = TenantType.INDIVIDUAL,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> TenantContext:
    """Set the tenant context for the current request."""
    context = TenantContext(
        tenant_id=tenant_id,
        tenant_type=tenant_type,
        user_id=user_id,
        request_id=request_id,
        metadata=metadata
    )
    
    # Set context variables
    current_tenant.set(tenant_id)
    if user_id:
        current_user_id.set(user_id)
    if request_id:
        _request_id_context.set(request_id)
    
    logger.debug(f"Set tenant context: {context.to_dict()}")
    return context

def clear_tenant_context():
    """Clear the tenant context."""
    current_tenant.set(None)
    current_user_id.set(None)
    _request_id_context.set(None)
    logger.debug("Cleared tenant context")

def get_tenant_context() -> Optional[TenantContext]:
    """Get the full tenant context."""
    tenant_id = get_current_tenant()
    if not tenant_id:
        return None
    
    return TenantContext(
        tenant_id=tenant_id,
        user_id=get_current_user(),
        request_id=get_current_request_id()
    )

def require_tenant() -> str:
    """Require a tenant context and return the tenant ID."""
    tenant_id = get_current_tenant()
    if not tenant_id:
        raise ValueError("No tenant context available")
    return tenant_id

def require_user() -> str:
    """Require a user context and return the user ID."""
    user_id = get_current_user()
    if not user_id:
        raise ValueError("No user context available")
    return user_id
