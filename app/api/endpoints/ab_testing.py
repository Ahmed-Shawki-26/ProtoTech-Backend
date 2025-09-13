# app/api/endpoints/ab_testing.py

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta

from app.core.tenant_context import get_current_tenant, get_tenant_context
from app.core.feature_flags import feature_flags
from app.services.unified_pricing_engine import unified_pricing_engine
from app.core.monitoring.metrics import metrics

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/experiments")
async def get_experiments():
    """Get all A/B testing experiments."""
    try:
        tenant_id = get_current_tenant()
        ab_status = unified_pricing_engine.get_ab_test_status()
        
        return JSONResponse(content={
            "experiments": ab_status["experiments"],
            "active_experiments": ab_status["active_experiments"],
            "tenant_id": tenant_id
        })
        
    except Exception as e:
        logger.error(f"Error getting experiments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get experiments")

@router.get("/experiments/{experiment_name}")
async def get_experiment(experiment_name: str):
    """Get specific experiment details."""
    try:
        tenant_id = get_current_tenant()
        user_id = None  # TODO: Get from auth context
        
        # Get experiment details
        ab_status = unified_pricing_engine.get_ab_test_status()
        if experiment_name not in ab_status["experiments"]:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        experiment = ab_status["experiments"][experiment_name]
        
        # Get user's variant
        variant = unified_pricing_engine.ab_test_manager.get_variant(
            experiment_name, user_id, tenant_id
        )
        
        return JSONResponse(content={
            "experiment": experiment,
            "user_variant": variant,
            "tenant_id": tenant_id,
            "user_id": user_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment {experiment_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get experiment")

@router.post("/experiments/{experiment_name}/variant")
async def get_user_variant(
    experiment_name: str,
    user_id: Optional[str] = Body(None),
    tenant_id: Optional[str] = Body(None)
):
    """Get or assign user variant for experiment."""
    try:
        # Use provided IDs or get from context
        if not user_id:
            user_id = None  # TODO: Get from auth context
        if not tenant_id:
            tenant_id = get_current_tenant()
        
        variant = unified_pricing_engine.ab_test_manager.get_variant(
            experiment_name, user_id, tenant_id
        )
        
        variant_config = unified_pricing_engine.ab_test_manager.get_experiment_config(
            experiment_name, variant
        )
        
        return JSONResponse(content={
            "experiment_name": experiment_name,
            "variant": variant,
            "variant_config": variant_config,
            "user_id": user_id,
            "tenant_id": tenant_id
        })
        
    except Exception as e:
        logger.error(f"Error getting user variant: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user variant")

@router.post("/experiments")
async def create_experiment(experiment_data: Dict[str, Any]):
    """Create a new A/B testing experiment."""
    try:
        # Validate required fields
        required_fields = ["name", "description", "variants"]
        for field in required_fields:
            if field not in experiment_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        experiment_name = experiment_data["name"]
        
        # Check if experiment already exists
        ab_status = unified_pricing_engine.get_ab_test_status()
        if experiment_name in ab_status["experiments"]:
            raise HTTPException(status_code=409, detail="Experiment already exists")
        
        # Create experiment
        experiment = {
            "name": experiment_data["name"],
            "description": experiment_data["description"],
            "variants": experiment_data["variants"],
            "active": experiment_data.get("active", True),
            "start_date": datetime.now(),
            "end_date": datetime.now() + timedelta(days=experiment_data.get("duration_days", 30))
        }
        
        unified_pricing_engine.ab_test_manager.experiments[experiment_name] = experiment
        
        logger.info(f"Created new experiment: {experiment_name}")
        
        return JSONResponse(content={
            "message": "Experiment created successfully",
            "experiment": experiment
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating experiment: {e}")
        raise HTTPException(status_code=500, detail="Failed to create experiment")

@router.put("/experiments/{experiment_name}")
async def update_experiment(experiment_name: str, update_data: Dict[str, Any]):
    """Update an existing experiment."""
    try:
        ab_status = unified_pricing_engine.get_ab_test_status()
        if experiment_name not in ab_status["experiments"]:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        experiment = ab_status["experiments"][experiment_name]
        
        # Update allowed fields
        allowed_fields = ["description", "variants", "active", "end_date"]
        for field, value in update_data.items():
            if field in allowed_fields:
                experiment[field] = value
        
        logger.info(f"Updated experiment: {experiment_name}")
        
        return JSONResponse(content={
            "message": "Experiment updated successfully",
            "experiment": experiment
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating experiment: {e}")
        raise HTTPException(status_code=500, detail="Failed to update experiment")

@router.delete("/experiments/{experiment_name}")
async def delete_experiment(experiment_name: str):
    """Delete an experiment."""
    try:
        ab_status = unified_pricing_engine.get_ab_test_status()
        if experiment_name not in ab_status["experiments"]:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        # Deactivate instead of deleting to preserve data
        experiment = ab_status["experiments"][experiment_name]
        experiment["active"] = False
        
        logger.info(f"Deactivated experiment: {experiment_name}")
        
        return JSONResponse(content={
            "message": "Experiment deactivated successfully",
            "experiment": experiment
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting experiment: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete experiment")

@router.get("/experiments/{experiment_name}/results")
async def get_experiment_results(experiment_name: str):
    """Get experiment results and analytics."""
    try:
        ab_status = unified_pricing_engine.get_ab_test_status()
        if experiment_name not in ab_status["experiments"]:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        experiment = ab_status["experiments"][experiment_name]
        
        # TODO: Implement actual analytics collection
        # For now, return mock data
        results = {
            "experiment_name": experiment_name,
            "status": "active" if experiment["active"] else "inactive",
            "start_date": experiment["start_date"].isoformat(),
            "end_date": experiment["end_date"].isoformat(),
            "variants": {},
            "total_participants": 0,
            "conversion_rate": 0.0,
            "statistical_significance": 0.0
        }
        
        # Mock variant results
        for variant_name, variant_config in experiment["variants"].items():
            results["variants"][variant_name] = {
                "participants": 0,  # TODO: Count actual participants
                "conversion_rate": 0.0,  # TODO: Calculate actual conversion
                "revenue": 0.0,  # TODO: Calculate actual revenue
                "avg_order_value": 0.0  # TODO: Calculate actual AOV
            }
        
        return JSONResponse(content=results)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get experiment results")

@router.post("/experiments/{experiment_name}/force-variant")
async def force_user_variant(
    experiment_name: str,
    user_id: str = Body(...),
    variant: str = Body(...),
    tenant_id: Optional[str] = Body(None)
):
    """Force a specific variant for a user (for testing)."""
    try:
        if not tenant_id:
            tenant_id = get_current_tenant()
        
        ab_status = unified_pricing_engine.get_ab_test_status()
        if experiment_name not in ab_status["experiments"]:
            raise HTTPException(status_code=404, detail="Experiment not found")
        
        experiment = ab_status["experiments"][experiment_name]
        if variant not in experiment["variants"]:
            raise HTTPException(status_code=400, detail="Invalid variant")
        
        # Store forced variant (in production, this would be in a database)
        forced_variants_key = f"forced_variants:{experiment_name}"
        # TODO: Implement forced variant storage
        
        logger.info(f"Forced variant {variant} for user {user_id} in experiment {experiment_name}")
        
        return JSONResponse(content={
            "message": f"User {user_id} forced to variant {variant}",
            "experiment_name": experiment_name,
            "variant": variant,
            "tenant_id": tenant_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error forcing user variant: {e}")
        raise HTTPException(status_code=500, detail="Failed to force user variant")

@router.get("/analytics/summary")
async def get_ab_testing_analytics():
    """Get A/B testing analytics summary."""
    try:
        tenant_id = get_current_tenant()
        ab_status = unified_pricing_engine.get_ab_test_status()
        
        # Calculate summary statistics
        total_experiments = len(ab_status["experiments"])
        active_experiments = ab_status["active_experiments"]
        
        # TODO: Implement actual analytics
        summary = {
            "total_experiments": total_experiments,
            "active_experiments": active_experiments,
            "completed_experiments": total_experiments - active_experiments,
            "tenant_id": tenant_id,
            "recent_activity": [],  # TODO: Implement activity tracking
            "top_performing_variants": [],  # TODO: Implement performance tracking
            "conversion_improvements": {}  # TODO: Implement conversion tracking
        }
        
        return JSONResponse(content=summary)
        
    except Exception as e:
        logger.error(f"Error getting A/B testing analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")

@router.post("/test/pricing")
async def test_pricing_with_ab(
    params: Dict[str, Any] = Body(...),
    dimensions: Dict[str, Any] = Body(...),
    user_id: Optional[str] = Body(None),
    tenant_id: Optional[str] = Body(None)
):
    """Test pricing calculation with A/B testing."""
    try:
        if not tenant_id:
            tenant_id = get_current_tenant()
        
        # Convert to proper objects (simplified for testing)
        from app.schemas.pcb import ManufacturingParameters, BaseMaterial, MinViaHole, BoardOutlineTolerance
        from app.schemas.pcb import BoardDimensions
        
        # Create parameters object
        manufacturing_params = ManufacturingParameters(
            quantity=params.get("quantity", 5),
            base_material=BaseMaterial(params.get("base_material", "FR-4")),
            min_via_hole_size_dia=MinViaHole(params.get("min_via_hole_size_dia", "0.3")),
            board_outline_tolerance=BoardOutlineTolerance(params.get("board_outline_tolerance", "±0.2mm (Regular)"))
        )
        
        # Create dimensions object
        board_dimensions = BoardDimensions(
            width_mm=dimensions.get("width_mm", 50.0),
            height_mm=dimensions.get("height_mm", 50.0)
        )
        
        # Calculate price with A/B testing
        result = await unified_pricing_engine.calculate_price(
            manufacturing_params,
            board_dimensions,
            tenant_id,
            user_id
        )
        
        return JSONResponse(content={
            "pricing_result": {
                "base_price": result.base_price,
                "final_price": result.final_price,
                "multipliers": result.multipliers,
                "ab_test_variant": result.ab_test_variant,
                "engine_version": result.engine_version,
                "calculation_time_ms": result.calculation_time_ms,
                "from_cache": result.from_cache
            },
            "test_info": {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "experiment": "pricing_algorithm"
            }
        })
        
    except Exception as e:
        logger.error(f"Error testing pricing with A/B: {e}")
        raise HTTPException(status_code=500, detail="Failed to test pricing")
