# app/services/pricing_cache.py

import time
import json
import hashlib
import logging
from typing import Optional, Dict, Any
from dataclasses import asdict

from app.services.pricing_models import PriceResult
from app.core.metrics import PricingMetrics

logger = logging.getLogger(__name__)

class PricingCache:
    """
    Multi-layer caching system for pricing calculations.
    L1: In-memory cache (instant access)
    L2: File-based cache (persistent)
    L3: Redis cache (shared across instances) - Future implementation
    """
    
    def __init__(self, memory_size_limit: int = 1000, file_cache_ttl: int = 3600):
        self.memory_cache: Dict[str, PriceResult] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0
        }
        self.memory_size_limit = memory_size_limit
        self.file_cache_ttl = file_cache_ttl
        
        logger.info(f"PricingCache initialized with memory limit: {memory_size_limit}")
    
    async def get(self, cache_key: str) -> Optional[PriceResult]:
        """
        Get cached pricing result.
        
        Args:
            cache_key: Cache key to lookup
            
        Returns:
            Cached PriceResult or None if not found
        """
        try:
            # L1: Memory cache (instant access)
            if cache_key in self.memory_cache:
                result = self.memory_cache[cache_key]
                
                # Check if cache entry is still valid
                if self._is_cache_entry_valid(result):
                    self.cache_stats["hits"] += 1
                    PricingMetrics.record_cache_hit("memory")
                    logger.debug(f"Memory cache hit: {cache_key}")
                    return result
                else:
                    # Remove expired entry
                    del self.memory_cache[cache_key]
                    logger.debug(f"Expired cache entry removed: {cache_key}")
            
            # L2: File cache (persistent)
            file_result = await self._get_from_file_cache(cache_key)
            if file_result:
                # Promote to memory cache
                self._add_to_memory_cache(cache_key, file_result)
                self.cache_stats["hits"] += 1
                PricingMetrics.record_cache_hit("file")
                logger.debug(f"File cache hit: {cache_key}")
                return file_result
            
            # Cache miss
            self.cache_stats["misses"] += 1
            logger.debug(f"Cache miss: {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"Cache get operation failed: {e}")
            self.cache_stats["misses"] += 1
            return None
    
    async def set(self, cache_key: str, result: PriceResult, ttl: int = None) -> bool:
        """
        Cache pricing result.
        
        Args:
            cache_key: Cache key
            result: PriceResult to cache
            ttl: Time to live in seconds (defaults to file_cache_ttl)
            
        Returns:
            True if successfully cached
        """
        try:
            if ttl is None:
                ttl = self.file_cache_ttl
            
            # Add metadata for cache management
            result.metadata["cached_at"] = time.time()
            result.metadata["cache_ttl"] = ttl
            result.metadata["cache_key"] = cache_key
            
            # L1: Add to memory cache
            self._add_to_memory_cache(cache_key, result)
            
            # L2: Add to file cache
            await self._set_file_cache(cache_key, result, ttl)
            
            self.cache_stats["sets"] += 1
            logger.debug(f"Result cached: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Cache set operation failed: {e}")
            return False
    
    def _add_to_memory_cache(self, cache_key: str, result: PriceResult):
        """Add result to memory cache with size management."""
        # Check if we need to evict entries
        if len(self.memory_cache) >= self.memory_size_limit:
            self._evict_oldest_entries()
        
        self.memory_cache[cache_key] = result
    
    def _evict_oldest_entries(self, evict_count: int = None):
        """Evict oldest entries from memory cache."""
        if evict_count is None:
            evict_count = max(1, self.memory_size_limit // 10)  # Evict 10% of cache
        
        # Sort by cached_at timestamp
        sorted_items = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].metadata.get("cached_at", 0)
        )
        
        # Remove oldest entries
        for cache_key, _ in sorted_items[:evict_count]:
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
                self.cache_stats["evictions"] += 1
        
        logger.debug(f"Evicted {evict_count} cache entries")
    
    def _is_cache_entry_valid(self, result: PriceResult) -> bool:
        """Check if cache entry is still valid."""
        cached_at = result.metadata.get("cached_at", 0)
        cache_ttl = result.metadata.get("cache_ttl", self.file_cache_ttl)
        return time.time() - cached_at < cache_ttl
    
    async def _get_from_file_cache(self, cache_key: str) -> Optional[PriceResult]:
        """Get result from file cache."""
        try:
            import os
            cache_dir = "cache/pricing"
            os.makedirs(cache_dir, exist_ok=True)
            
            # Create filename from cache key hash
            filename = hashlib.md5(cache_key.encode()).hexdigest() + ".json"
            filepath = os.path.join(cache_dir, filename)
            
            if not os.path.exists(filepath):
                return None
            
            # Check file age
            file_age = time.time() - os.path.getmtime(filepath)
            if file_age > self.file_cache_ttl:
                os.remove(filepath)  # Remove expired file
                return None
            
            # Load from file
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Handle both old and new cache formats
            if 'base_price' in data and 'final_price' in data:
                # New unified pricing format
                result = PriceResult(**data)
            else:
                # Old pricing format - convert to new format
                result = PriceResult(
                    base_price=data.get('direct_cost_egp', 0),
                    multipliers=data.get('details', {}).get('multipliers', {}),
                    final_price=data.get('final_price_egp', 0),
                    breakdown=data.get('details', {}),
                    from_cache=True,
                    calculation_time_ms=data.get('details', {}).get('calculation_time_ms', 0),
                    engine_version="1.0.0"
                )
            
            logger.debug(f"Loaded from file cache: {cache_key}")
            return result
            
        except Exception as e:
            logger.warning(f"File cache read failed: {e}")
            return None
    
    async def _set_file_cache(self, cache_key: str, result: PriceResult, ttl: int):
        """Store result in file cache."""
        try:
            import os
            cache_dir = "cache/pricing"
            os.makedirs(cache_dir, exist_ok=True)
            
            # Create filename from cache key hash
            filename = hashlib.md5(cache_key.encode()).hexdigest() + ".json"
            filepath = os.path.join(cache_dir, filename)
            
            # Convert to JSON-serializable format
            data = result.to_dict()
            
            # Write to file
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Stored in file cache: {cache_key}")
            
        except Exception as e:
            logger.warning(f"File cache write failed: {e}")
    
    async def clear(self, cache_type: str = "all") -> int:
        """
        Clear cache entries.
        
        Args:
            cache_type: "memory", "file", or "all"
            
        Returns:
            Number of entries cleared
        """
        cleared_count = 0
        
        try:
            if cache_type in ["memory", "all"]:
                cleared_count += len(self.memory_cache)
                self.memory_cache.clear()
                logger.info(f"Cleared {cleared_count} memory cache entries")
            
            if cache_type in ["file", "all"]:
                import os
                import glob
                
                cache_dir = "cache/pricing"
                if os.path.exists(cache_dir):
                    files = glob.glob(os.path.join(cache_dir, "*.json"))
                    for file in files:
                        os.remove(file)
                    cleared_count += len(files)
                    logger.info(f"Cleared {len(files)} file cache entries")
            
            return cleared_count
            
        except Exception as e:
            logger.error(f"Cache clear operation failed: {e}")
            return cleared_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "memory_cache_size": len(self.memory_cache),
            "memory_cache_limit": self.memory_size_limit,
            "hit_rate_percent": round(hit_rate, 2),
            "total_hits": self.cache_stats["hits"],
            "total_misses": self.cache_stats["misses"],
            "total_sets": self.cache_stats["sets"],
            "total_evictions": self.cache_stats["evictions"],
            "cache_ttl_seconds": self.file_cache_ttl
        }
    
    async def preload_common_configurations(self):
        """Preload cache with common pricing configurations."""
        logger.info("Preloading common pricing configurations...")
        
        # Common configurations to preload
        common_configs = [
            {"quantity": 5, "base_material": "FR-4", "thickness": "1.6"},
            {"quantity": 10, "base_material": "FR-4", "thickness": "1.6"},
            {"quantity": 5, "base_material": "Aluminum", "thickness": "1.6"},
            {"quantity": 1, "base_material": "FR-4", "thickness": "1.6"},
        ]
        
        # Standard board sizes
        standard_sizes = [
            {"width_mm": 100, "height_mm": 100, "area_m2": 0.01},  # 10x10cm
            {"width_mm": 50, "height_mm": 50, "area_m2": 0.0025},  # 5x5cm
            {"width_mm": 25, "height_mm": 25, "area_m2": 0.000625}, # 2.5x2.5cm
        ]
        
        preloaded_count = 0
        for config in common_configs:
            for size in standard_sizes:
                try:
                    # Create mock parameters for preloading
                    from app.schemas.pcb import ManufacturingParameters, BoardDimensions
                    
                    params = ManufacturingParameters(**config)
                    dimensions = BoardDimensions(**size)
                    
                    # Generate cache key
                    cache_key = f"preload:{hashlib.md5(json.dumps({**config, **size}, sort_keys=True).encode()).hexdigest()}"
                    
                    # Create mock result (this would normally be calculated)
                    from app.services.pricing_models import PriceResult, PriceBreakdown, Multipliers, PricingResultStatus
                    
                    mock_result = PriceResult(
                        status=PricingResultStatus.SUCCESS,
                        breakdown=PriceBreakdown(
                            base_price_egp=size["area_m2"] * 10000 * 1.5,
                            material_cost_egp=0,
                            quantity_cost_egp=0,
                            thickness_cost_egp=0,
                            copper_cost_egp=0,
                            via_hole_cost_egp=0,
                            tolerance_cost_egp=0,
                            color_cost_egp=0,
                            surface_finish_cost_egp=0,
                            shipping_cost_egp=45.0,
                            customs_rate_egp=0,
                            tax_amount_egp=0
                        ),
                        multipliers=Multipliers(),
                        calculation_time_ms=0.1,
                        cache_key=cache_key
                    )
                    
                    await self.set(cache_key, mock_result)
                    preloaded_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to preload config {config}: {e}")
        
        logger.info(f"Preloaded {preloaded_count} common configurations")

# Global pricing cache instance
pricing_cache = PricingCache()
