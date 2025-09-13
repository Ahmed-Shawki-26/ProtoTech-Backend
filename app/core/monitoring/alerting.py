# app/core/monitoring/alerting.py

from typing import Dict, Any, List, Optional, Callable
import logging
import time
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

@dataclass
class Alert:
    """Alert definition."""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata or {}
        }

class AlertRule:
    """Alert rule definition."""
    
    def __init__(
        self,
        name: str,
        description: str,
        severity: AlertSeverity,
        condition: Callable[[], bool],
        threshold: float,
        duration: int = 300,  # 5 minutes default
        cooldown: int = 600   # 10 minutes default
    ):
        self.name = name
        self.description = description
        self.severity = severity
        self.condition = condition
        self.threshold = threshold
        self.duration = duration
        self.cooldown = cooldown
        self.last_triggered: Optional[datetime] = None
        self.active_alerts: List[Alert] = []

class AlertManager:
    """Manages alerts and alerting rules."""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_handlers: List[Callable[[Alert], None]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")
    
    def add_handler(self, handler: Callable[[Alert], None]):
        """Add an alert handler."""
        self.alert_handlers.append(handler)
        logger.info(f"Added alert handler: {handler.__name__}")
    
    async def start(self):
        """Start the alert manager."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert manager started")
    
    async def stop(self):
        """Stop the alert manager."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Alert manager stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_rules()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _check_rules(self):
        """Check all alert rules."""
        for rule in self.rules:
            try:
                await self._check_rule(rule)
            except Exception as e:
                logger.error(f"Error checking rule {rule.name}: {e}")
    
    async def _check_rule(self, rule: AlertRule):
        """Check a single alert rule."""
        try:
            # Check if condition is met
            if not rule.condition():
                # Condition not met, resolve any active alerts
                await self._resolve_rule_alerts(rule)
                return
            
            # Check cooldown period
            if rule.last_triggered:
                time_since_triggered = datetime.now() - rule.last_triggered
                if time_since_triggered.total_seconds() < rule.cooldown:
                    return
            
            # Create new alert
            await self._create_alert(rule)
            rule.last_triggered = datetime.now()
            
        except Exception as e:
            logger.error(f"Error checking rule {rule.name}: {e}")
    
    async def _create_alert(self, rule: AlertRule):
        """Create a new alert."""
        alert_id = f"{rule.name}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            name=rule.name,
            description=rule.description,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            created_at=datetime.now(),
            metadata={
                "threshold": rule.threshold,
                "duration": rule.duration,
                "rule_name": rule.name
            }
        )
        
        self.active_alerts[alert_id] = alert
        rule.active_alerts.append(alert)
        
        # Notify handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler {handler.__name__}: {e}")
        
        logger.warning(f"Alert triggered: {alert.name} - {alert.description}")
    
    async def _resolve_rule_alerts(self, rule: AlertRule):
        """Resolve alerts for a rule."""
        for alert in rule.active_alerts[:]:  # Copy list to avoid modification during iteration
            if alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                del self.active_alerts[alert.id]
                rule.active_alerts.remove(alert)
                logger.info(f"Alert resolved: {alert.name}")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return [alert for alert in self.active_alerts.values() 
                if alert.status == AlertStatus.ACTIVE]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get alerts by severity."""
        return [alert for alert in self.active_alerts.values() 
                if alert.severity == severity and alert.status == AlertStatus.ACTIVE]

# Global alert manager instance
alert_manager = AlertManager()

# Alert handlers
def log_alert_handler(alert: Alert):
    """Log alert to application logs."""
    logger.warning(f"ALERT: {alert.name} - {alert.description}")

def console_alert_handler(alert: Alert):
    """Print alert to console."""
    print(f"🚨 ALERT [{alert.severity.value.upper()}]: {alert.name}")
    print(f"   {alert.description}")
    print(f"   Created: {alert.created_at}")

def email_alert_handler(alert: Alert):
    """Send alert via email (placeholder)."""
    # TODO: Implement email sending
    logger.info(f"Email alert would be sent for: {alert.name}")

def slack_alert_handler(alert: Alert):
    """Send alert to Slack (placeholder)."""
    # TODO: Implement Slack integration
    logger.info(f"Slack alert would be sent for: {alert.name}")

# Initialize alert handlers
alert_manager.add_handler(log_alert_handler)
alert_manager.add_handler(console_alert_handler)

# Define common alert rules
def create_pricing_error_rate_rule():
    """Create alert rule for high pricing error rate."""
    from app.core.monitoring.metrics import pricing_errors, pricing_requests
    
    def check_error_rate():
        try:
            # Get error count from last 5 minutes
            error_samples = pricing_errors.collect()[0].samples
            request_samples = pricing_requests.collect()[0].samples
            
            total_errors = sum(sample.value for sample in error_samples)
            total_requests = sum(sample.value for sample in request_samples)
            
            if total_requests == 0:
                return False
            
            error_rate = total_errors / total_requests
            return error_rate > 0.05  # 5% error rate threshold
            
        except Exception as e:
            logger.error(f"Error checking pricing error rate: {e}")
            return False
    
    return AlertRule(
        name="high_pricing_error_rate",
        description="Pricing error rate exceeds 5%",
        severity=AlertSeverity.HIGH,
        condition=check_error_rate,
        threshold=0.05,
        duration=300,
        cooldown=600
    )

def create_slow_pricing_rule():
    """Create alert rule for slow pricing calculations."""
    from app.core.monitoring.metrics import pricing_duration
    
    def check_slow_pricing():
        try:
            # Check if 95th percentile is above 1 second
            samples = pricing_duration.collect()[0].samples
            if not samples:
                return False
            
            # Simple check - in production, use proper percentile calculation
            return len(samples) > 0  # Placeholder logic
            
        except Exception as e:
            logger.error(f"Error checking slow pricing: {e}")
            return False
    
    return AlertRule(
        name="slow_pricing_calculations",
        description="Pricing calculations are slow (p95 > 1s)",
        severity=AlertSeverity.MEDIUM,
        condition=check_slow_pricing,
        threshold=1.0,
        duration=300,
        cooldown=600
    )

def create_cache_miss_rate_rule():
    """Create alert rule for high cache miss rate."""
    from app.core.monitoring.metrics import cache_hits, cache_misses
    
    def check_cache_miss_rate():
        try:
            hit_samples = cache_hits.collect()[0].samples
            miss_samples = cache_misses.collect()[0].samples
            
            total_hits = sum(sample.value for sample in hit_samples)
            total_misses = sum(sample.value for sample in miss_samples)
            
            if total_hits + total_misses == 0:
                return False
            
            miss_rate = total_misses / (total_hits + total_misses)
            return miss_rate > 0.3  # 30% miss rate threshold
            
        except Exception as e:
            logger.error(f"Error checking cache miss rate: {e}")
            return False
    
    return AlertRule(
        name="high_cache_miss_rate",
        description="Cache miss rate exceeds 30%",
        severity=AlertSeverity.MEDIUM,
        condition=check_cache_miss_rate,
        threshold=0.3,
        duration=300,
        cooldown=600
    )

# Initialize common alert rules
alert_manager.add_rule(create_pricing_error_rate_rule())
alert_manager.add_rule(create_slow_pricing_rule())
alert_manager.add_rule(create_cache_miss_rate_rule())
