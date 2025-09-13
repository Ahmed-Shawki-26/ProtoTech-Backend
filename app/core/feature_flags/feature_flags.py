# app/core/feature_flags/feature_flags.py

from typing import Dict, Any, Optional, List, Callable
from enum import Enum
import logging
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class FeatureFlagType(Enum):
    """Types of feature flags."""
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    TENANT_LIST = "tenant_list"
    TIME_BASED = "time_based"

class FeatureFlagStatus(Enum):
    """Feature flag status."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    ROLLING_OUT = "rolling_out"
    ROLLED_BACK = "rolled_back"

@dataclass
class FeatureFlag:
    """Feature flag definition."""
    name: str
    description: str
    flag_type: FeatureFlagType
    status: FeatureFlagStatus
    default_value: Any
    rollout_percentage: float = 0.0
    enabled_users: List[str] = None
    enabled_tenants: List[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.enabled_users is None:
            self.enabled_users = []
        if self.enabled_tenants is None:
            self.enabled_tenants = []
        if self.metadata is None:
            self.metadata = {}

class FeatureFlagManager:
    """Manages feature flags and their evaluation."""
    
    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {}
        self.evaluation_cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        self._load_default_flags()
    
    def _load_default_flags(self):
        """Load default feature flags."""
        default_flags = [
            FeatureFlag(
                name="new_pricing_engine",
                description="Enable new pricing engine with improved performance",
                flag_type=FeatureFlagType.PERCENTAGE,
                status=FeatureFlagStatus.ROLLING_OUT,
                default_value=False,
                rollout_percentage=25.0,
                metadata={"version": "2.0.0", "team": "pricing"}
            ),
            FeatureFlag(
                name="enhanced_caching",
                description="Enable enhanced multi-layer caching",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ENABLED,
                default_value=True,
                metadata={"version": "2.0.0", "team": "infrastructure"}
            ),
            FeatureFlag(
                name="tenant_isolation",
                description="Enable tenant isolation middleware",
                flag_type=FeatureFlagType.TENANT_LIST,
                status=FeatureFlagStatus.ROLLING_OUT,
                default_value=False,
                enabled_tenants=["enterprise", "partner"],
                metadata={"version": "2.0.0", "team": "platform"}
            ),
            FeatureFlag(
                name="advanced_monitoring",
                description="Enable advanced monitoring and alerting",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.ENABLED,
                default_value=True,
                metadata={"version": "2.0.0", "team": "observability"}
            ),
            FeatureFlag(
                name="load_testing_endpoints",
                description="Enable load testing endpoints",
                flag_type=FeatureFlagType.BOOLEAN,
                status=FeatureFlagStatus.DISABLED,
                default_value=False,
                metadata={"version": "2.0.0", "team": "testing"}
            ),
            FeatureFlag(
                name="beta_features",
                description="Enable beta features for testing",
                flag_type=FeatureFlagType.USER_LIST,
                status=FeatureFlagStatus.ROLLING_OUT,
                default_value=False,
                enabled_users=["admin", "beta_tester"],
                metadata={"version": "2.0.0", "team": "product"}
            )
        ]
        
        for flag in default_flags:
            self.flags[flag.name] = flag
        
        logger.info(f"Loaded {len(default_flags)} default feature flags")
    
    def add_flag(self, flag: FeatureFlag):
        """Add a new feature flag."""
        self.flags[flag.name] = flag
        logger.info(f"Added feature flag: {flag.name}")
    
    def update_flag(self, name: str, **kwargs):
        """Update an existing feature flag."""
        if name not in self.flags:
            raise ValueError(f"Feature flag '{name}' not found")
        
        flag = self.flags[name]
        for key, value in kwargs.items():
            if hasattr(flag, key):
                setattr(flag, key, value)
        
        # Clear cache for this flag
        self.evaluation_cache.pop(name, None)
        
        logger.info(f"Updated feature flag: {name}")
    
    def remove_flag(self, name: str):
        """Remove a feature flag."""
        if name in self.flags:
            del self.flags[name]
            self.evaluation_cache.pop(name, None)
            logger.info(f"Removed feature flag: {name}")
    
    def is_enabled(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if a feature flag is enabled."""
        try:
            # Check cache first
            cache_key = f"{flag_name}:{user_id}:{tenant_id}"
            if cache_key in self.evaluation_cache:
                cached_result, timestamp = self.evaluation_cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    return cached_result
            
            # Evaluate flag
            result = self._evaluate_flag(flag_name, user_id, tenant_id, context)
            
            # Cache result
            self.evaluation_cache[cache_key] = (result, time.time())
            
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating feature flag '{flag_name}': {e}")
            # Return default value on error
            flag = self.flags.get(flag_name)
            return flag.default_value if flag else False
    
    def _evaluate_flag(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Evaluate a feature flag based on its type and rules."""
        flag = self.flags.get(flag_name)
        if not flag:
            logger.warning(f"Feature flag '{flag_name}' not found")
            return False
        
        # Check status
        if flag.status == FeatureFlagStatus.DISABLED:
            return False
        elif flag.status == FeatureFlagStatus.ENABLED:
            return True
        
        # Evaluate based on flag type
        if flag.flag_type == FeatureFlagType.BOOLEAN:
            return flag.default_value
        
        elif flag.flag_type == FeatureFlagType.PERCENTAGE:
            return self._evaluate_percentage_flag(flag, user_id, tenant_id)
        
        elif flag.flag_type == FeatureFlagType.USER_LIST:
            return self._evaluate_user_list_flag(flag, user_id)
        
        elif flag.flag_type == FeatureFlagType.TENANT_LIST:
            return self._evaluate_tenant_list_flag(flag, tenant_id)
        
        elif flag.flag_type == FeatureFlagType.TIME_BASED:
            return self._evaluate_time_based_flag(flag)
        
        return flag.default_value
    
    def _evaluate_percentage_flag(
        self,
        flag: FeatureFlag,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Evaluate percentage-based rollout."""
        if flag.status != FeatureFlagStatus.ROLLING_OUT:
            return flag.default_value
        
        # Use user_id or tenant_id for consistent hashing
        identifier = user_id or tenant_id or "default"
        
        # Simple hash-based percentage
        hash_value = hash(f"{flag.name}:{identifier}") % 100
        return hash_value < flag.rollout_percentage
    
    def _evaluate_user_list_flag(self, flag: FeatureFlag, user_id: Optional[str]) -> bool:
        """Evaluate user list flag."""
        if not user_id:
            return flag.default_value
        
        return user_id in flag.enabled_users
    
    def _evaluate_tenant_list_flag(self, flag: FeatureFlag, tenant_id: Optional[str]) -> bool:
        """Evaluate tenant list flag."""
        if not tenant_id:
            return flag.default_value
        
        return tenant_id in flag.enabled_tenants
    
    def _evaluate_time_based_flag(self, flag: FeatureFlag) -> bool:
        """Evaluate time-based flag."""
        now = datetime.now()
        
        if flag.start_time and now < flag.start_time:
            return False
        
        if flag.end_time and now > flag.end_time:
            return False
        
        return True
    
    def get_flag_value(
        self,
        flag_name: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Get the value of a feature flag."""
        flag = self.flags.get(flag_name)
        if not flag:
            return None
        
        if flag.flag_type == FeatureFlagType.BOOLEAN:
            return self.is_enabled(flag_name, user_id, tenant_id, context)
        else:
            return self.is_enabled(flag_name, user_id, tenant_id, context)
    
    def get_all_flags(self) -> Dict[str, FeatureFlag]:
        """Get all feature flags."""
        return self.flags.copy()
    
    def get_flags_for_user(self, user_id: str) -> Dict[str, bool]:
        """Get all enabled flags for a user."""
        return {
            name: self.is_enabled(name, user_id=user_id)
            for name in self.flags.keys()
        }
    
    def get_flags_for_tenant(self, tenant_id: str) -> Dict[str, bool]:
        """Get all enabled flags for a tenant."""
        return {
            name: self.is_enabled(name, tenant_id=tenant_id)
            for name in self.flags.keys()
        }
    
    def export_config(self) -> Dict[str, Any]:
        """Export feature flag configuration."""
        return {
            "flags": {
                name: {
                    "name": flag.name,
                    "description": flag.description,
                    "type": flag.flag_type.value,
                    "status": flag.status.value,
                    "default_value": flag.default_value,
                    "rollout_percentage": flag.rollout_percentage,
                    "enabled_users": flag.enabled_users,
                    "enabled_tenants": flag.enabled_tenants,
                    "start_time": flag.start_time.isoformat() if flag.start_time else None,
                    "end_time": flag.end_time.isoformat() if flag.end_time else None,
                    "metadata": flag.metadata
                }
                for name, flag in self.flags.items()
            },
            "exported_at": datetime.now().isoformat()
        }
    
    def import_config(self, config: Dict[str, Any]):
        """Import feature flag configuration."""
        try:
            flags_data = config.get("flags", {})
            
            for name, flag_data in flags_data.items():
                flag = FeatureFlag(
                    name=flag_data["name"],
                    description=flag_data["description"],
                    flag_type=FeatureFlagType(flag_data["type"]),
                    status=FeatureFlagStatus(flag_data["status"]),
                    default_value=flag_data["default_value"],
                    rollout_percentage=flag_data.get("rollout_percentage", 0.0),
                    enabled_users=flag_data.get("enabled_users", []),
                    enabled_tenants=flag_data.get("enabled_tenants", []),
                    start_time=datetime.fromisoformat(flag_data["start_time"]) if flag_data.get("start_time") else None,
                    end_time=datetime.fromisoformat(flag_data["end_time"]) if flag_data.get("end_time") else None,
                    metadata=flag_data.get("metadata", {})
                )
                
                self.flags[name] = flag
            
            # Clear cache
            self.evaluation_cache.clear()
            
            logger.info(f"Imported {len(flags_data)} feature flags")
            
        except Exception as e:
            logger.error(f"Error importing feature flag configuration: {e}")
            raise

# Global feature flag manager instance
feature_flags = FeatureFlagManager()

# Convenience functions
def is_feature_enabled(
    flag_name: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> bool:
    """Check if a feature is enabled."""
    return feature_flags.is_enabled(flag_name, user_id, tenant_id)

def get_feature_value(
    flag_name: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Any:
    """Get feature flag value."""
    return feature_flags.get_flag_value(flag_name, user_id, tenant_id)

# Import time for caching
import time
