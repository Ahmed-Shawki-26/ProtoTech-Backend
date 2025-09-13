# app/core/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry, generate_latest
from typing import Dict, Any, Optional
import time
import logging
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Create a custom registry for our metrics
registry = CollectorRegistry()

# Request metrics
pricing_requests = Counter(
    'pricing_requests_total',
    'Total pricing requests',
    ['material', 'status', 'tenant_id'],
    registry=registry
)

pricing_duration = Histogram(
    'pricing_duration_seconds',
    'Pricing calculation duration',
    ['operation', 'tenant_id'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

pricing_errors = Counter(
    'pricing_errors_total',
    'Total pricing errors',
    ['error_code', 'tenant_id'],
    registry=registry
)

cache_hits = Counter(
    'pricing_cache_hits_total',
    'Cache hit rate',
    ['cache_level', 'tenant_id'],
    registry=registry
)

cache_misses = Counter(
    'pricing_cache_misses_total',
    'Cache miss rate',
    ['cache_level', 'tenant_id'],
    registry=registry
)

# System metrics
active_connections = Gauge(
    'active_connections',
    'Number of active connections',
    registry=registry
)

memory_usage = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes',
    registry=registry
)

cpu_usage = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage',
    registry=registry
)

# Business metrics
quotes_generated = Counter(
    'quotes_generated_total',
    'Total quotes generated',
    ['material', 'tenant_id'],
    registry=registry
)

orders_created = Counter(
    'orders_created_total',
    'Total orders created',
    ['status', 'tenant_id'],
    registry=registry
)

revenue_total = Counter(
    'revenue_total_egp',
    'Total revenue in EGP',
    ['tenant_id'],
    registry=registry
)

# Application info
app_info = Info(
    'app_info',
    'Application information',
    registry=registry
)

# Set application info
app_info.info({
    'version': '2.0.0',
    'service': 'prototech-pricing',
    'environment': 'production'
})

class MetricsCollector:
    """Centralized metrics collection and management."""
    
    def __init__(self):
        self.registry = registry
        self._start_time = time.time()
    
    def record_pricing_request(self, material: str, status: str, tenant_id: str = "default"):
        """Record a pricing request."""
        pricing_requests.labels(
            material=material,
            status=status,
            tenant_id=tenant_id
        ).inc()
    
    def record_pricing_error(self, error_code: str, tenant_id: str = "default"):
        """Record a pricing error."""
        pricing_errors.labels(
            error_code=error_code,
            tenant_id=tenant_id
        ).inc()
    
    def record_cache_hit(self, cache_level: str, tenant_id: str = "default"):
        """Record a cache hit."""
        cache_hits.labels(
            cache_level=cache_level,
            tenant_id=tenant_id
        ).inc()
    
    def record_cache_miss(self, cache_level: str, tenant_id: str = "default"):
        """Record a cache miss."""
        cache_misses.labels(
            cache_level=cache_level,
            tenant_id=tenant_id
        ).inc()
    
    def record_quote_generated(self, material: str, tenant_id: str = "default"):
        """Record a quote generation."""
        quotes_generated.labels(
            material=material,
            tenant_id=tenant_id
        ).inc()
    
    def record_order_created(self, status: str, tenant_id: str = "default"):
        """Record an order creation."""
        orders_created.labels(
            status=status,
            tenant_id=tenant_id
        ).inc()
    
    def record_revenue(self, amount: float, tenant_id: str = "default"):
        """Record revenue."""
        revenue_total.labels(tenant_id=tenant_id).inc(amount)
    
    def update_system_metrics(self):
        """Update system metrics."""
        try:
            import psutil
            
            # Memory usage
            memory_info = psutil.virtual_memory()
            memory_usage.set(memory_info.used)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_usage.set(cpu_percent)
            
        except ImportError:
            logger.warning("psutil not available for system metrics")
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics."""
        return {
            "uptime_seconds": time.time() - self._start_time,
            "registry_size": len(list(self.registry.collect())),
            "timestamp": time.time()
        }

# Global metrics collector instance
metrics = MetricsCollector()

def time_operation(operation_name: str, tenant_id: str = "default"):
    """Decorator to time operations and record metrics."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with pricing_duration.labels(
                operation=operation_name,
                tenant_id=tenant_id
            ).time():
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with pricing_duration.labels(
                operation=operation_name,
                tenant_id=tenant_id
            ).time():
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

@contextmanager
def track_cache_operation(cache_level: str, tenant_id: str = "default"):
    """Context manager to track cache operations."""
    try:
        yield
        metrics.record_cache_hit(cache_level, tenant_id)
    except KeyError:
        metrics.record_cache_miss(cache_level, tenant_id)
        raise

def get_health_metrics() -> Dict[str, Any]:
    """Get health metrics for the application."""
    try:
        metrics.update_system_metrics()
        
        return {
            "metrics": {
                "total_requests": sum([
                    sample.value for sample in pricing_requests.collect()[0].samples
                ]),
                "total_errors": sum([
                    sample.value for sample in pricing_errors.collect()[0].samples
                ]),
                "cache_hit_rate": _calculate_cache_hit_rate(),
                "system": {
                    "memory_usage_bytes": memory_usage._value._value,
                    "cpu_usage_percent": cpu_usage._value._value
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        return {"error": str(e)}

def _calculate_cache_hit_rate() -> float:
    """Calculate cache hit rate."""
    try:
        hits = sum([sample.value for sample in cache_hits.collect()[0].samples])
        misses = sum([sample.value for sample in cache_misses.collect()[0].samples])
        
        if hits + misses == 0:
            return 0.0
        
        return hits / (hits + misses)
    except Exception:
        return 0.0

def generate_metrics_response():
    """Generate Prometheus metrics response."""
    return generate_latest(registry)

# Import asyncio for the decorator
import asyncio
