# app/services/config_loader.py

import yaml
import os
import logging
from typing import Dict, Any, List, Tuple
from pathlib import Path

from app.services.pricing_rules_engine import PricingConfig

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Loads and manages configuration from YAML files."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._config_cache: Dict[str, Any] = {}
        logger.info(f"ConfigLoader initialized with config directory: {self.config_dir}")
    
    def load_pricing_config(self) -> PricingConfig:
        """
        Load pricing configuration from YAML file.
        
        Returns:
            PricingConfig object with loaded configuration
        """
        try:
            config_file = self.config_dir / "pricing_config.yaml"
            
            if not config_file.exists():
                logger.warning(f"Pricing config file not found: {config_file}")
                return PricingConfig()  # Return default config
            
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Extract configuration sections
            pricing_config = PricingConfig(
                material_multipliers=config_data.get("material_multipliers", {}),
                quantity_brackets=config_data.get("quantity_brackets", []),
                thickness_multipliers=config_data.get("thickness_multipliers", {}),
                copper_weight_multipliers=config_data.get("copper_weight_multipliers", {}),
                via_hole_multipliers=config_data.get("via_hole_multipliers", {}),
                tolerance_multipliers=config_data.get("tolerance_multipliers", {}),
                color_multipliers=config_data.get("color_multipliers", {}),
                surface_finish_multipliers=config_data.get("surface_finish_multipliers", {})
            )
            
            logger.info("Pricing configuration loaded successfully")
            return pricing_config
            
        except Exception as e:
            logger.error(f"Failed to load pricing configuration: {e}")
            return PricingConfig()  # Return default config
    
    def load_base_pricing_config(self) -> Dict[str, Any]:
        """Load base pricing configuration."""
        try:
            config_file = self.config_dir / "pricing_config.yaml"
            
            if not config_file.exists():
                return {}
            
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            return config_data.get("base_pricing", {})
            
        except Exception as e:
            logger.error(f"Failed to load base pricing configuration: {e}")
            return {}
    
    def load_validation_config(self) -> Dict[str, Any]:
        """Load validation configuration."""
        try:
            config_file = self.config_dir / "pricing_config.yaml"
            
            if not config_file.exists():
                return {}
            
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            return config_data.get("validation", {})
            
        except Exception as e:
            logger.error(f"Failed to load validation configuration: {e}")
            return {}
    
    def load_cache_config(self) -> Dict[str, Any]:
        """Load cache configuration."""
        try:
            config_file = self.config_dir / "pricing_config.yaml"
            
            if not config_file.exists():
                return {}
            
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            return config_data.get("cache", {})
            
        except Exception as e:
            logger.error(f"Failed to load cache configuration: {e}")
            return {}
    
    def load_supported_values(self) -> Dict[str, List[str]]:
        """Load supported values configuration."""
        try:
            config_file = self.config_dir / "pricing_config.yaml"
            
            if not config_file.exists():
                return {}
            
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            return config_data.get("supported_values", {})
            
        except Exception as e:
            logger.error(f"Failed to load supported values configuration: {e}")
            return {}
    
    def reload_config(self, config_name: str = None) -> bool:
        """
        Reload configuration from file.
        
        Args:
            config_name: Specific config to reload, or None for all
            
        Returns:
            True if reload was successful
        """
        try:
            if config_name:
                # Reload specific config
                if config_name in self._config_cache:
                    del self._config_cache[config_name]
            else:
                # Reload all configs
                self._config_cache.clear()
            
            logger.info(f"Configuration reloaded: {config_name or 'all'}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def get_config(self, config_name: str) -> Any:
        """Get cached configuration."""
        return self._config_cache.get(config_name)
    
    def set_config(self, config_name: str, config_data: Any):
        """Set cached configuration."""
        self._config_cache[config_name] = config_data
    
    def validate_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate configuration data.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            List of validation warnings/errors
        """
        warnings = []
        
        try:
            # Validate material multipliers
            material_multipliers = config_data.get("material_multipliers", {})
            for material, multiplier in material_multipliers.items():
                if not isinstance(multiplier, (int, float)) or multiplier <= 0:
                    warnings.append(f"Invalid material multiplier for {material}: {multiplier}")
            
            # Validate quantity brackets
            quantity_brackets = config_data.get("quantity_brackets", [])
            for i, (quantity, multiplier) in enumerate(quantity_brackets):
                if not isinstance(quantity, int) or quantity <= 0:
                    warnings.append(f"Invalid quantity in bracket {i}: {quantity}")
                if not isinstance(multiplier, (int, float)) or multiplier <= 0:
                    warnings.append(f"Invalid multiplier in bracket {i}: {multiplier}")
            
            # Validate base pricing
            base_pricing = config_data.get("base_pricing", {})
            if "price_per_cm2" in base_pricing:
                price = base_pricing["price_per_cm2"]
                if not isinstance(price, (int, float)) or price <= 0:
                    warnings.append(f"Invalid base price per cm²: {price}")
            
            # Check for missing required sections
            required_sections = [
                "material_multipliers", "quantity_brackets", "thickness_multipliers",
                "copper_weight_multipliers", "via_hole_multipliers", "tolerance_multipliers"
            ]
            
            for section in required_sections:
                if section not in config_data:
                    warnings.append(f"Missing required configuration section: {section}")
            
            logger.debug(f"Configuration validation completed: {len(warnings)} warnings")
            return warnings
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return [f"Configuration validation failed: {str(e)}"]
    
    def save_config(self, config_data: Dict[str, Any], filename: str = "pricing_config.yaml") -> bool:
        """
        Save configuration to YAML file.
        
        Args:
            config_data: Configuration data to save
            filename: Configuration filename
            
        Returns:
            True if save was successful
        """
        try:
            config_file = self.config_dir / filename
            
            # Validate before saving
            warnings = self.validate_config(config_data)
            if warnings:
                logger.warning(f"Configuration has warnings: {warnings}")
            
            # Ensure config directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Save configuration
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
            logger.info(f"Configuration saved successfully: {config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of loaded configurations."""
        return {
            "config_directory": str(self.config_dir),
            "cached_configs": list(self._config_cache.keys()),
            "available_files": [f.name for f in self.config_dir.glob("*.yaml")],
            "total_cached_size": len(str(self._config_cache))
        }

# Global config loader instance
config_loader = ConfigLoader()
