# app/services/unified_pricing_engine.py

from typing import Dict, Any, Optional, List, Union
import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json

from app.core.tenant_context import get_current_tenant, get_tenant_context
from app.core.feature_flags import feature_flags, is_feature_enabled
from app.core.monitoring.metrics import metrics, time_operation
from app.core.exceptions import PricingError, ErrorCode
from app.services.pricing_rules_engine import PricingRulesEngine, PricingConfig
from app.services.price_calculator import PriceCalculator
from app.services.tenant_aware_pricing_engine import TenantAwarePricingEngine
from app.schemas.pcb import ManufacturingParameters, BoardDimensions

logger = logging.getLogger(__name__)

@dataclass
class PriceResult:
    """Comprehensive pricing result."""
    base_price: float
    multipliers: Dict[str, float]
    final_price: float
    breakdown: Dict[str, Any]
    from_cache: bool = False
    cache_key: Optional[str] = None
    calculation_time_ms: float = 0.0
    engine_version: str = "2.0.0"
    tenant_id: Optional[str] = None
    ab_test_variant: Optional[str] = None

@dataclass
class CacheConfig:
    """Cache configuration."""
    enabled: bool = True
    ttl_seconds: int = 3600  # 1 hour
    max_size: int = 10000
    preload_enabled: bool = True
    compression_enabled: bool = True

class AdvancedCache:
    """Advanced multi-layer caching system."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.memory_cache: Dict[str, Any] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0
        }
        self._preload_common_configs()
    
    def _generate_cache_key(self, params: dict, dimensions: dict, tenant_id: str) -> str:
        """Generate deterministic cache key."""
        # Normalize and sort for consistency
        normalized = {
            "params": dict(sorted(params.items())),
            "dimensions": dict(sorted(dimensions.items())),
            "tenant_id": tenant_id
        }
        key_string = json.dumps(normalized, sort_keys=True)
        return f"price:v2:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    async def get(self, key: str) -> Optional[PriceResult]:
        """Get from cache."""
        if not self.config.enabled:
            return None
        
        if key in self.memory_cache:
            self.cache_stats["hits"] += 1
            logger.debug(f"Cache hit: {key}")
            return self.memory_cache[key]
        
        self.cache_stats["misses"] += 1
        logger.debug(f"Cache miss: {key}")
        return None
    
    async def set(self, key: str, value: PriceResult, ttl: Optional[int] = None):
        """Set cache value."""
        if not self.config.enabled:
            return
        
        # Check cache size limit
        if len(self.memory_cache) >= self.config.max_size:
            self._evict_oldest()
        
        # Store in memory cache
        self.memory_cache[key] = value
        self.cache_stats["sets"] += 1
        
        logger.debug(f"Cache set: {key}")
    
    def _evict_oldest(self):
        """Evict oldest cache entries."""
        if self.memory_cache:
            # Simple FIFO eviction
            oldest_key = next(iter(self.memory_cache))
            del self.memory_cache[oldest_key]
            self.cache_stats["evictions"] += 1
    
    def _preload_common_configs(self):
        """Preload common pricing configurations."""
        if not self.config.preload_enabled:
            return
        
        common_configs = [
            {"material": "FR-4", "quantity": 5, "thickness": "1.6mm"},
            {"material": "FR-4", "quantity": 10, "thickness": "1.6mm"},
            {"material": "Aluminum", "quantity": 5, "thickness": "1.6mm"},
            {"material": "Flex", "quantity": 5, "thickness": "1.6mm"},
        ]
        
        standard_sizes = [
            {"width": 50, "height": 50},   # 5x5cm
            {"width": 100, "height": 100}, # 10x10cm
            {"width": 25, "height": 25},   # 2.5x2.5cm
        ]
        
        # Preload combinations
        for config in common_configs:
            for size in standard_sizes:
                key = self._generate_cache_key(config, size, "default")
                # Mark as preloaded (will be calculated on first access)
                self.memory_cache[key] = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = self.cache_stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "enabled": self.config.enabled,
            "size": len(self.memory_cache),
            "max_size": self.config.max_size,
            "hit_rate": hit_rate,
            "stats": self.cache_stats.copy()
        }

class ABTestManager:
    """A/B testing manager for pricing strategies."""
    
    def __init__(self):
        self.experiments: Dict[str, Dict[str, Any]] = {}
        self._load_default_experiments()
    
    def _load_default_experiments(self):
        """Load default A/B testing experiments."""
        self.experiments = {
            "pricing_algorithm": {
                "name": "Pricing Algorithm Optimization",
                "description": "Test different pricing algorithms",
                "variants": {
                    "control": {"weight": 50, "algorithm": "legacy"},
                    "variant_a": {"weight": 25, "algorithm": "optimized"},
                    "variant_b": {"weight": 25, "algorithm": "ml_based"}
                },
                "active": True,
                "start_date": datetime.now(),
                "end_date": datetime.now() + timedelta(days=30)
            },
            "discount_strategy": {
                "name": "Discount Strategy Testing",
                "description": "Test different discount approaches",
                "variants": {
                    "control": {"weight": 50, "discount_type": "none"},
                    "variant_a": {"weight": 25, "discount_type": "volume"},
                    "variant_b": {"weight": 25, "discount_type": "loyalty"}
                },
                "active": True,
                "start_date": datetime.now(),
                "end_date": datetime.now() + timedelta(days=14)
            }
        }
    
    def get_variant(self, experiment_name: str, user_id: Optional[str] = None, tenant_id: Optional[str] = None) -> str:
        """Get A/B test variant for user/tenant."""
        if experiment_name not in self.experiments:
            return "control"
        
        experiment = self.experiments[experiment_name]
        if not experiment["active"]:
            return "control"
        
        # Check if experiment is still active
        now = datetime.now()
        if now < experiment["start_date"] or now > experiment["end_date"]:
            return "control"
        
        # Use user_id or tenant_id for consistent assignment
        identifier = user_id or tenant_id or "default"
        
        # Simple hash-based assignment
        hash_value = hash(f"{experiment_name}:{identifier}") % 100
        
        # Assign variant based on weights
        cumulative_weight = 0
        for variant_name, variant_config in experiment["variants"].items():
            cumulative_weight += variant_config["weight"]
            if hash_value < cumulative_weight:
                return variant_name
        
        return "control"
    
    def get_experiment_config(self, experiment_name: str, variant: str) -> Dict[str, Any]:
        """Get configuration for specific experiment variant."""
        if experiment_name not in self.experiments:
            return {}
        
        experiment = self.experiments[experiment_name]
        if variant not in experiment["variants"]:
            return {}
        
        return experiment["variants"][variant]

class UnifiedPricingEngine:
    """Unified pricing engine with advanced features."""
    
    def __init__(self):
        self.cache_config = CacheConfig()
        self.cache = AdvancedCache(self.cache_config)
        self.ab_test_manager = ABTestManager()
        self.tenant_aware_engine = TenantAwarePricingEngine()
        self.price_calculator = PriceCalculator()
        self.rules_engine = PricingRulesEngine()
        
        logger.info("UnifiedPricingEngine initialized with advanced features")
    
    @time_operation("unified_pricing_calculation")
    async def calculate_price(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        force_calculation: bool = False
    ) -> PriceResult:
        """Calculate price using unified engine with all advanced features."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Get tenant context
            if not tenant_id:
                tenant_id = get_current_tenant() or "default"
            
            # Generate cache key
            params_dict = self._params_to_dict(params)
            dimensions_dict = self._dimensions_to_dict(dimensions)
            cache_key = self.cache._generate_cache_key(params_dict, dimensions_dict, tenant_id)
            
            # Check cache first (unless forced)
            if not force_calculation:
                try:
                    cached_result = await self.cache.get(cache_key)
                    if cached_result:
                        cached_result.from_cache = True
                        cached_result.cache_key = cache_key
                        metrics.record_cache_hit("memory", tenant_id)
                        return cached_result
                except Exception as e:
                    logger.warning(f"Cache read error, proceeding with calculation: {e}")
                    metrics.record_cache_miss("error", tenant_id)
            
            # Get A/B test variant
            ab_variant = self.ab_test_manager.get_variant("pricing_algorithm", user_id, tenant_id)
            
            # Calculate price based on variant
            if ab_variant == "control":
                result = await self._calculate_legacy_price(params, dimensions, tenant_id)
            elif ab_variant == "variant_a":
                result = await self._calculate_optimized_price(params, dimensions, tenant_id)
            elif ab_variant == "variant_b":
                result = await self._calculate_ml_price(params, dimensions, tenant_id)
            else:
                result = await self._calculate_legacy_price(params, dimensions, tenant_id)
            
            # Add A/B test information
            result.ab_test_variant = ab_variant
            result.tenant_id = tenant_id
            result.cache_key = cache_key
            
            # Calculate processing time
            end_time = asyncio.get_event_loop().time()
            result.calculation_time_ms = (end_time - start_time) * 1000
            
            # Cache the result
            try:
                await self.cache.set(cache_key, result)
            except Exception as e:
                logger.warning(f"Cache write error: {e}")
                # Continue without caching
            
            # Record metrics
            metrics.record_pricing_request(
                material=params.base_material.value,
                status="success",
                tenant_id=tenant_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in unified pricing calculation: {e}")
            metrics.record_pricing_error("CALCULATION_FAILED", tenant_id or "unknown")
            raise PricingError(
                code=ErrorCode.PRICING_CALCULATION_FAILED,
                user_message="Failed to calculate pricing",
                technical_details=str(e),
                context={"tenant_id": tenant_id, "ab_variant": ab_variant}
            )
    
    async def _calculate_legacy_price(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        tenant_id: str
    ) -> PriceResult:
        """Calculate price using legacy algorithm."""
        multipliers = self.rules_engine.calculate_multipliers(params)
        base_price = self.price_calculator.calculate_base_price(dimensions, params)
        
        total_multiplier = multipliers.total()
        final_price = base_price * total_multiplier
        
        return PriceResult(
            base_price=base_price,
            multipliers=multipliers.__dict__,
            final_price=final_price,
            breakdown=self._generate_breakdown(base_price, multipliers),
            engine_version="1.0.0"
        )
    
    async def _calculate_optimized_price(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        tenant_id: str
    ) -> PriceResult:
        """Calculate price using optimized algorithm."""
        # Use tenant-aware engine for optimized pricing
        result_dict = await self.tenant_aware_engine.calculate_price(params, dimensions, tenant_id)
        
        return PriceResult(
            base_price=result_dict["base_price"],
            multipliers=result_dict["multipliers"],
            final_price=result_dict["final_price"],
            breakdown=result_dict.get("breakdown", {}),
            engine_version="2.0.0"
        )
    
    async def _calculate_ml_price(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        tenant_id: str
    ) -> PriceResult:
        """Calculate price using ML-based algorithm (placeholder)."""
        # For now, use optimized pricing with ML adjustments
        result = await self._calculate_optimized_price(params, dimensions, tenant_id)
        
        # Apply ML-based adjustments (placeholder)
        ml_adjustment = 1.0  # TODO: Implement actual ML model
        
        result.final_price *= ml_adjustment
        result.engine_version = "2.0.0-ml"
        
        return result
    
    def _params_to_dict(self, params: ManufacturingParameters) -> dict:
        """Convert parameters to dictionary."""
        return {
            "quantity": params.quantity,
            "base_material": params.base_material.value,
            "min_via_hole_size_dia": params.min_via_hole_size_dia.value,
            "board_outline_tolerance": params.board_outline_tolerance.value,
            "pcb_thickness_mm": getattr(params, 'pcb_thickness_mm', '1.6mm'),
            "outer_copper_weight": getattr(params, 'outer_copper_weight', '1 oz'),
            "pcb_color": getattr(params, 'pcb_color', 'green'),
            "surface_finish": getattr(params, 'surface_finish', 'HASL'),
            "silkscreen": getattr(params, 'silkscreen', 'white')
        }
    
    def _dimensions_to_dict(self, dimensions: BoardDimensions) -> dict:
        """Convert dimensions to dictionary."""
        return {
            "width_mm": dimensions.width_mm,
            "height_mm": dimensions.height_mm
        }
    
    def _generate_breakdown(self, base_price: float, multipliers) -> Dict[str, Any]:
        """Generate price breakdown."""
        return {
            "base_price": base_price,
            "material_cost": base_price * multipliers.material,
            "quantity_adjustment": base_price * (multipliers.quantity - 1),
            "specification_costs": base_price * (multipliers.total() - multipliers.material - multipliers.quantity + 1),
            "total_multiplier": multipliers.total()
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def get_ab_test_status(self) -> Dict[str, Any]:
        """Get A/B testing status."""
        return {
            "experiments": self.ab_test_manager.experiments,
            "active_experiments": len([e for e in self.ab_test_manager.experiments.values() if e["active"]])
        }
    
    def clear_cache(self):
        """Clear all cache."""
        self.cache.memory_cache.clear()
        logger.info("Cache cleared")

# Global unified pricing engine instance
unified_pricing_engine = UnifiedPricingEngine()
