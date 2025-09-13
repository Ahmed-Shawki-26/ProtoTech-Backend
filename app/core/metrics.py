# app/core/metrics.py

import time
import logging
from typing import Dict, Any, Optional
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Simple in-memory metrics storage (replace with Prometheus in production)
class MetricsCollector:
    """Simple metrics collector for development and testing."""
    
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.histograms: Dict[str, list] = {}
        self.gauges: Dict[str, float] = {}
    
    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value
        logger.debug(f"Counter {key}: {self.counters[key]}")
    
    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
        logger.debug(f"Histogram {key}: {len(self.histograms[key])} observations")
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self.gauges[key] = value
        logger.debug(f"Gauge {key}: {value}")
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create a key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_counter(self, name: str, labels: Dict[str, str] = None) -> int:
        """Get counter value."""
        key = self._make_key(name, labels)
        return self.counters.get(key, 0)
    
    def get_histogram_stats(self, name: str, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self.histograms.get(key, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values)
        }
    
    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get gauge value."""
        key = self._make_key(name, labels)
        return self.gauges.get(key, 0)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics for debugging."""
        return {
            "counters": self.counters,
            "histograms": {k: self.get_histogram_stats(k.split('{')[0]) for k in self.histograms.keys()},
            "gauges": self.gauges
        }

# Global metrics collector instance
metrics = MetricsCollector()

# Convenience functions
def increment_counter(name: str, value: int = 1, labels: Dict[str, str] = None):
    """Increment a counter metric."""
    metrics.increment_counter(name, value, labels)

def observe_histogram(name: str, value: float, labels: Dict[str, str] = None):
    """Record a histogram observation."""
    metrics.observe_histogram(name, value, labels)

def set_gauge(name: str, value: float, labels: Dict[str, str] = None):
    """Set a gauge value."""
    metrics.set_gauge(name, value, labels)

# Timing decorator
def time_function(metric_name: str, labels: Dict[str, str] = None):
    """Decorator to time function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                observe_histogram(metric_name, duration, labels)
        return wrapper
    return decorator

# Context manager for timing
@contextmanager
def time_operation(metric_name: str, labels: Dict[str, str] = None):
    """Context manager to time operations."""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        observe_histogram(metric_name, duration, labels)

# Specific metrics for our application
class PricingMetrics:
    """Metrics specific to pricing operations."""
    
    @staticmethod
    def record_pricing_request(material: str, status: str):
        """Record a pricing request."""
        increment_counter("pricing_requests_total", labels={"material": material, "status": status})
    
    @staticmethod
    def record_pricing_duration(operation: str, duration: float):
        """Record pricing calculation duration."""
        observe_histogram("pricing_duration_seconds", duration, labels={"operation": operation})
    
    @staticmethod
    def record_pricing_error(error_code: str):
        """Record a pricing error."""
        increment_counter("pricing_errors_total", labels={"error_code": error_code})
    
    @staticmethod
    def record_cache_hit(cache_level: str):
        """Record a cache hit."""
        increment_counter("pricing_cache_hits_total", labels={"cache_level": cache_level})

class FileProcessingMetrics:
    """Metrics specific to file processing."""
    
    @staticmethod
    def record_file_upload(file_type: str, size_bytes: int):
        """Record file upload."""
        increment_counter("file_uploads_total", labels={"file_type": file_type})
        observe_histogram("file_size_bytes", size_bytes, labels={"file_type": file_type})
    
    @staticmethod
    def record_processing_duration(operation: str, duration: float):
        """Record file processing duration."""
        observe_histogram("file_processing_duration_seconds", duration, labels={"operation": operation})
    
    @staticmethod
    def record_processing_error(operation: str, error_type: str):
        """Record file processing error."""
        increment_counter("file_processing_errors_total", labels={"operation": operation, "error_type": error_type})

# Health check endpoint data
def get_health_metrics() -> Dict[str, Any]:
    """Get metrics for health check endpoint."""
    return {
        "metrics": metrics.get_all_metrics(),
        "timestamp": time.time()
    }
