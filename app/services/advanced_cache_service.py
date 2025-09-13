# app/services/advanced_cache_service.py

from typing import Dict, Any, Optional, List, Union
import logging
import asyncio
import json
import pickle
import gzip
from datetime import datetime, timedelta
import hashlib

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from app.core.tenant_context import get_current_tenant
from app.core.monitoring.metrics import metrics

logger = logging.getLogger(__name__)

class RedisCacheService:
    """Advanced Redis-based caching service."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
        self.compression_enabled = True
        self.key_prefix = "prototech:v2:"
        
    async def connect(self):
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using memory cache only")
            return False
        
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            self.connected = True
            logger.info("Connected to Redis successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Disconnected from Redis")
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage."""
        try:
            # Try JSON first for readability
            json_data = json.dumps(value, default=str)
            if self.compression_enabled and len(json_data) > 1024:  # Compress if > 1KB
                return gzip.compress(json_data.encode())
            return json_data.encode()
        except (TypeError, ValueError):
            # Fallback to pickle for complex objects
            pickled_data = pickle.dumps(value)
            if self.compression_enabled and len(pickled_data) > 1024:
                return gzip.compress(pickled_data)
            return pickled_data
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        try:
            # Try decompression first
            try:
                decompressed = gzip.decompress(data)
            except (OSError, EOFError):
                decompressed = data
            
            # Try JSON first
            try:
                return json.loads(decompressed.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fallback to pickle
                return pickle.loads(decompressed)
        except Exception as e:
            logger.error(f"Failed to deserialize cache value: {e}")
            return None
    
    def _generate_key(self, key: str, tenant_id: Optional[str] = None) -> str:
        """Generate namespaced cache key."""
        if not tenant_id:
            tenant_id = get_current_tenant() or "default"
        return f"{self.key_prefix}{tenant_id}:{key}"
    
    async def get(self, key: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        """Get value from cache."""
        if not self.connected:
            return None
        
        try:
            cache_key = self._generate_key(key, tenant_id)
            data = await self.redis_client.get(cache_key)
            
            if data is None:
                metrics.record_cache_miss("redis", tenant_id or "default")
                return None
            
            value = self._deserialize_value(data)
            metrics.record_cache_hit("redis", tenant_id or "default")
            return value
            
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Set value in cache."""
        if not self.connected:
            return False
        
        try:
            cache_key = self._generate_key(key, tenant_id)
            serialized_value = self._serialize_value(value)
            
            await self.redis_client.setex(cache_key, ttl, serialized_value)
            return True
            
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete value from cache."""
        if not self.connected:
            return False
        
        try:
            cache_key = self._generate_key(key, tenant_id)
            result = await self.redis_client.delete(cache_key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Check if key exists."""
        if not self.connected:
            return False
        
        try:
            cache_key = self._generate_key(key, tenant_id)
            return await self.redis_client.exists(cache_key)
            
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics."""
        if not self.connected:
            return {"connected": False}
        
        try:
            info = await self.redis_client.info()
            return {
                "connected": True,
                "used_memory": info.get("used_memory_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {"connected": False, "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict[str, Any]) -> float:
        """Calculate cache hit rate."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        return hits / total if total > 0 else 0.0
    
    async def clear_tenant_cache(self, tenant_id: str) -> int:
        """Clear all cache entries for a tenant."""
        if not self.connected:
            return 0
        
        try:
            pattern = f"{self.key_prefix}{tenant_id}:*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error(f"Redis clear tenant cache error: {e}")
            return 0
    
    async def warm_cache(self, common_configs: List[Dict[str, Any]]):
        """Warm cache with common configurations."""
        if not self.connected:
            return
        
        logger.info(f"Warming cache with {len(common_configs)} configurations")
        
        for config in common_configs:
            try:
                # Generate cache key
                key_data = json.dumps(config, sort_keys=True)
                cache_key = hashlib.md5(key_data.encode()).hexdigest()
                
                # Store configuration
                await self.set(f"config:{cache_key}", config, ttl=7200)
                
            except Exception as e:
                logger.error(f"Cache warming error: {e}")
        
        logger.info("Cache warming completed")

class MultiLayerCache:
    """Multi-layer caching system (Memory + Redis)."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.memory_cache: Dict[str, Any] = {}
        self.redis_cache = RedisCacheService(redis_url) if redis_url else None
        self.memory_ttl: Dict[str, datetime] = {}
        self.max_memory_size = 1000
        self.memory_ttl_seconds = 300  # 5 minutes
        
    async def initialize(self):
        """Initialize the multi-layer cache."""
        if self.redis_cache:
            await self.redis_cache.connect()
    
    async def cleanup(self):
        """Cleanup cache resources."""
        if self.redis_cache:
            await self.redis_cache.disconnect()
    
    def _is_memory_expired(self, key: str) -> bool:
        """Check if memory cache entry is expired."""
        if key not in self.memory_ttl:
            return True
        
        return datetime.now() > self.memory_ttl[key]
    
    def _evict_memory_cache(self):
        """Evict expired entries from memory cache."""
        now = datetime.now()
        expired_keys = [
            key for key, expiry in self.memory_ttl.items()
            if now > expiry
        ]
        
        for key in expired_keys:
            self.memory_cache.pop(key, None)
            self.memory_ttl.pop(key, None)
    
    async def get(self, key: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        """Get value from multi-layer cache."""
        # Check memory cache first
        if key in self.memory_cache and not self._is_memory_expired(key):
            metrics.record_cache_hit("memory", tenant_id or "default")
            return self.memory_cache[key]
        
        # Check Redis cache
        if self.redis_cache and self.redis_cache.connected:
            value = await self.redis_cache.get(key, tenant_id)
            if value is not None:
                # Promote to memory cache
                await self.set(key, value, ttl=self.memory_ttl_seconds, tenant_id=tenant_id)
                return value
        
        metrics.record_cache_miss("multilayer", tenant_id or "default")
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Set value in multi-layer cache."""
        # Set in memory cache
        if len(self.memory_cache) >= self.max_memory_size:
            self._evict_memory_cache()
        
        self.memory_cache[key] = value
        self.memory_ttl[key] = datetime.now() + timedelta(seconds=min(ttl, self.memory_ttl_seconds))
        
        # Set in Redis cache
        if self.redis_cache and self.redis_cache.connected:
            return await self.redis_cache.set(key, value, ttl, tenant_id)
        
        return True
    
    async def delete(self, key: str, tenant_id: Optional[str] = None) -> bool:
        """Delete value from multi-layer cache."""
        # Remove from memory cache
        self.memory_cache.pop(key, None)
        self.memory_ttl.pop(key, None)
        
        # Remove from Redis cache
        if self.redis_cache and self.redis_cache.connected:
            return await self.redis_cache.delete(key, tenant_id)
        
        return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        memory_stats = {
            "memory_size": len(self.memory_cache),
            "memory_max_size": self.max_memory_size,
            "memory_utilization": len(self.memory_cache) / self.max_memory_size
        }
        
        redis_stats = {}
        if self.redis_cache:
            redis_stats = await self.redis_cache.get_stats()
        
        return {
            "memory": memory_stats,
            "redis": redis_stats,
            "multilayer_enabled": self.redis_cache is not None
        }
    
    async def clear_all(self, tenant_id: Optional[str] = None):
        """Clear all cache layers."""
        # Clear memory cache
        if tenant_id:
            # Clear tenant-specific entries
            keys_to_remove = [k for k in self.memory_cache.keys() if tenant_id in k]
            for key in keys_to_remove:
                self.memory_cache.pop(key, None)
                self.memory_ttl.pop(key, None)
        else:
            self.memory_cache.clear()
            self.memory_ttl.clear()
        
        # Clear Redis cache
        if self.redis_cache and self.redis_cache.connected:
            if tenant_id:
                await self.redis_cache.clear_tenant_cache(tenant_id)
            else:
                # Clear all Redis cache (use with caution)
                await self.redis_cache.redis_client.flushdb()

# Global cache service instance
advanced_cache = MultiLayerCache()
