# app/core/feature_flags.py

import os
from typing import Dict, Any
from functools import lru_cache

class FeatureFlags:
    """Simple feature flag system for gradual rollout"""
    
    def __init__(self):
        self.flags: Dict[str, bool] = {}
        self._load_flags()
    
    def _load_flags(self):
        """Load feature flags from environment variables"""
        # Default flags (disabled by default for safety)
        default_flags = {
            "pcb_client_recolor": False,
            "async_quote_generation": False,
            "progressive_image_loading": False,
        }
        
        # Override with environment variables
        for flag_name, default_value in default_flags.items():
            env_var = f"FF_{flag_name.upper()}"
            env_value = os.getenv(env_var, str(default_value).lower())
            self.flags[flag_name] = env_value.lower() in ('true', '1', 'yes', 'on')
    
    def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled"""
        return self.flags.get(flag_name, False)
    
    def is_disabled(self, flag_name: str) -> bool:
        """Check if a feature flag is disabled"""
        return not self.is_enabled(flag_name)
    
    def get_all_flags(self) -> Dict[str, bool]:
        """Get all feature flags (for debugging)"""
        return self.flags.copy()
    
    def set_flag(self, flag_name: str, enabled: bool):
        """Set a feature flag (for testing)"""
        self.flags[flag_name] = enabled

# Global instance
feature_flags = FeatureFlags()

# Convenience functions
def is_feature_enabled(flag_name: str) -> bool:
    """Check if a feature flag is enabled"""
    return feature_flags.is_enabled(flag_name)

def is_feature_disabled(flag_name: str) -> bool:
    """Check if a feature flag is disabled"""
    return feature_flags.is_disabled(flag_name)

# Common feature flag checks
def use_client_side_recoloring() -> bool:
    """Check if client-side recoloring is enabled"""
    return is_feature_enabled("pcb_client_recolor")

def use_async_quote_generation() -> bool:
    """Check if async quote generation is enabled"""
    return is_feature_enabled("async_quote_generation")

def use_progressive_image_loading() -> bool:
    """Check if progressive image loading is enabled"""
    return is_feature_enabled("progressive_image_loading")
