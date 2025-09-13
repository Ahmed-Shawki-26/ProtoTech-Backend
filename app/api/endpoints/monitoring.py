# app/api/endpoints/monitoring.py

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response, JSONResponse
from typing import Dict, Any, Optional, List
import logging
import asyncio

from app.core.monitoring.metrics import metrics, generate_metrics_response, get_health_metrics
from app.core.monitoring.alerting import alert_manager, Alert, AlertSeverity
from app.core.feature_flags import feature_flags
from app.core.tenant_context import get_current_tenant, get_tenant_context
from app.services.tenant_aware_pricing_engine import tenant_aware_pricing_engine

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/metrics", response_class=Response)
async def get_prometheus_metrics():
    """Get Prometheus metrics."""
    try:
        metrics_data = generate_metrics_response()
        return Response(
            content=metrics_data,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics")

@router.get("/health")
async def health_check():
    """Comprehensive health check endpoint."""
    try:
        health_data = get_health_metrics()
        
        # Add tenant context if available
        tenant_context = get_tenant_context()
        if tenant_context:
            health_data["tenant_context"] = tenant_context.to_dict()
        
        # Add feature flags status
        health_data["feature_flags"] = {
            "new_pricing_engine": feature_flags.is_enabled("new_pricing_engine"),
            "enhanced_caching": feature_flags.is_enabled("enhanced_caching"),
            "tenant_isolation": feature_flags.is_enabled("tenant_isolation"),
            "advanced_monitoring": feature_flags.is_enabled("advanced_monitoring")
        }
        
        return JSONResponse(content=health_data)
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@router.get("/alerts")
async def get_active_alerts():
    """Get all active alerts."""
    try:
        alerts = alert_manager.get_active_alerts()
        return JSONResponse(content={
            "alerts": [alert.to_dict() for alert in alerts],
            "count": len(alerts)
        })
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get alerts")

@router.get("/alerts/{severity}")
async def get_alerts_by_severity(severity: str):
    """Get alerts by severity level."""
    try:
        severity_enum = AlertSeverity(severity.lower())
        alerts = alert_manager.get_alerts_by_severity(severity_enum)
        return JSONResponse(content={
            "alerts": [alert.to_dict() for alert in alerts],
            "severity": severity,
            "count": len(alerts)
        })
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
    except Exception as e:
        logger.error(f"Error getting alerts by severity: {e}")
        raise HTTPException(status_code=500, detail="Failed to get alerts")

@router.get("/feature-flags")
async def get_feature_flags():
    """Get all feature flags."""
    try:
        tenant_id = get_current_tenant()
        
        if tenant_id:
            # Return tenant-specific flags
            flags = feature_flags.get_flags_for_tenant(tenant_id)
            return JSONResponse(content={
                "tenant_id": tenant_id,
                "flags": flags
            })
        else:
            # Return all flags
            all_flags = feature_flags.get_all_flags()
            return JSONResponse(content={
                "flags": {name: flag.__dict__ for name, flag in all_flags.items()}
            })
            
    except Exception as e:
        logger.error(f"Error getting feature flags: {e}")
        raise HTTPException(status_code=500, detail="Failed to get feature flags")

@router.get("/feature-flags/{flag_name}")
async def get_feature_flag(flag_name: str):
    """Get a specific feature flag."""
    try:
        tenant_id = get_current_tenant()
        user_id = None  # TODO: Get from auth context
        
        is_enabled = feature_flags.is_enabled(flag_name, user_id, tenant_id)
        flag_value = feature_flags.get_flag_value(flag_name, user_id, tenant_id)
        
        return JSONResponse(content={
            "flag_name": flag_name,
            "enabled": is_enabled,
            "value": flag_value,
            "tenant_id": tenant_id,
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Error getting feature flag {flag_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get feature flag")

@router.get("/tenant-config")
async def get_tenant_config():
    """Get tenant-specific configuration."""
    try:
        tenant_id = get_current_tenant()
        if not tenant_id:
            raise HTTPException(status_code=400, detail="No tenant context available")
        
        config = tenant_aware_pricing_engine.get_tenant_pricing_info(tenant_id)
        return JSONResponse(content=config)
        
    except Exception as e:
        logger.error(f"Error getting tenant config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tenant configuration")

@router.get("/tenant-config/all")
async def get_all_tenant_configs():
    """Get all tenant configurations (admin only)."""
    try:
        # TODO: Add admin authorization check
        configs = tenant_aware_pricing_engine.get_all_tenant_configs()
        return JSONResponse(content=configs)
        
    except Exception as e:
        logger.error(f"Error getting all tenant configs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tenant configurations")

@router.get("/system/status")
async def get_system_status():
    """Get comprehensive system status."""
    try:
        # Update system metrics
        metrics.update_system_metrics()
        
        # Get health metrics
        health_data = get_health_metrics()
        
        # Get active alerts
        alerts = alert_manager.get_active_alerts()
        
        # Get tenant context
        tenant_context = get_tenant_context()
        
        # Get feature flags status
        feature_flags_status = {
            "new_pricing_engine": feature_flags.is_enabled("new_pricing_engine"),
            "enhanced_caching": feature_flags.is_enabled("enhanced_caching"),
            "tenant_isolation": feature_flags.is_enabled("tenant_isolation"),
            "advanced_monitoring": feature_flags.is_enabled("advanced_monitoring"),
            "load_testing_endpoints": feature_flags.is_enabled("load_testing_endpoints")
        }
        
        return JSONResponse(content={
            "status": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "health": health_data,
            "alerts": {
                "active_count": len(alerts),
                "critical_count": len([a for a in alerts if a.severity == AlertSeverity.CRITICAL]),
                "high_count": len([a for a in alerts if a.severity == AlertSeverity.HIGH])
            },
            "tenant_context": tenant_context.to_dict() if tenant_context else None,
            "feature_flags": feature_flags_status,
            "system": {
                "uptime": health_data.get("uptime_seconds", 0),
                "version": "2.0.0"
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@router.post("/alerts/test")
async def test_alert_system():
    """Test the alert system (for development/testing)."""
    try:
        # Create a test alert
        test_alert = Alert(
            id="test_alert",
            name="Test Alert",
            description="This is a test alert to verify the alerting system",
            severity=AlertSeverity.LOW,
            status=AlertSeverity.ACTIVE,
            created_at=asyncio.get_event_loop().time(),
            metadata={"test": True}
        )
        
        # Trigger alert handlers
        for handler in alert_manager.alert_handlers:
            try:
                handler(test_alert)
            except Exception as e:
                logger.error(f"Error in test alert handler: {e}")
        
        return JSONResponse(content={
            "message": "Test alert triggered successfully",
            "alert": test_alert.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error testing alert system: {e}")
        raise HTTPException(status_code=500, detail="Failed to test alert system")

@router.get("/load-test/status")
async def get_load_test_status():
    """Get load testing status and results."""
    try:
        # Check if load testing is enabled
        if not feature_flags.is_enabled("load_testing_endpoints"):
            raise HTTPException(status_code=403, detail="Load testing endpoints are disabled")
        
        # TODO: Implement load test status tracking
        return JSONResponse(content={
            "status": "available",
            "message": "Load testing endpoints are enabled",
            "endpoints": [
                "/api/v1/monitoring/load-test/pricing",
                "/api/v1/monitoring/load-test/health",
                "/api/v1/monitoring/load-test/stress"
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting load test status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get load test status")
