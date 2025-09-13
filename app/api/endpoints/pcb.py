# app/api/endpoints/pcb.py

import os
import io
import json
import zipfile
import time
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import ValidationError

from app.services.quote_generator import QuoteGenerator
# We import the corrected schema that no longer has an 'images' field.
from app.schemas.pcb import ManufacturingParameters, GerberQuoteResponse, JobResponse, QuoteManifest, JobStatus
from app.core.feature_flags import feature_flags, use_client_side_recoloring
from app.services.price_calculator import PriceCalculator
from app.services.image_cache_service import image_cache
from app.services.local_pricing_service import LocalPricingService
from app.services.robust_pricing_service import RobustPricingService
from app.services.parameter_normalizer import ParameterNormalizer
from app.core.exceptions import ParameterValidationError, PricingError, raise_pricing_error
from app.core.metrics import PricingMetrics, time_operation, get_health_metrics

# Phase 4 imports - New unified pricing engine
from app.services.unified_pricing_engine import unified_pricing_engine
from app.core.tenant_context import get_current_tenant, get_tenant_context
from app.core.monitoring.metrics import metrics

router = APIRouter()

@router.get(
    "/health/",
    summary="Health Check with Advanced Metrics",
    description="Check the health of the PCB service with comprehensive monitoring"
)
async def health_check():
    """Health check endpoint with advanced metrics and monitoring."""
    try:
        # Get tenant context
        tenant_context = get_tenant_context()
        
        # Get comprehensive health data
        health_data = get_health_metrics()
        
        # Get unified pricing engine status
        cache_stats = unified_pricing_engine.get_cache_stats()
        ab_test_status = unified_pricing_engine.get_ab_test_status()
        
        # Get feature flags status
        feature_flags_status = {
            "new_pricing_engine": feature_flags.is_enabled("new_pricing_engine"),
            "enhanced_caching": feature_flags.is_enabled("enhanced_caching"),
            "tenant_isolation": feature_flags.is_enabled("tenant_isolation"),
            "advanced_monitoring": feature_flags.is_enabled("advanced_monitoring")
        }
        
        return JSONResponse(content={
            "status": "healthy",
            "service": "pcb-manufacturing",
            "version": "2.0.0",
            "tenant_context": tenant_context.to_dict() if tenant_context else None,
            "feature_flags": feature_flags_status,
            "pricing_engine": {
                "cache_stats": cache_stats,
                "ab_testing": ab_test_status
            },
            **health_data
        })
    except Exception as e:
        # Record error in metrics
        metrics.record_pricing_error("HEALTH_CHECK_FAILED", get_current_tenant() or "unknown")
        
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "pcb-manufacturing",
                "error": str(e),
                "tenant_context": get_current_tenant()
            }
        )

@router.post(
    "/generate-quote/",
    summary="Generate Full PCB Quote from Gerber ZIP",
    description="Upload a ZIP file and provide manufacturing options as a JSON string. Returns a new ZIP containing rendered images and a detailed quote.json file."
)
async def generate_full_quote(
    file: UploadFile = File(..., description="A ZIP file containing Gerber layers."),
    params_json: str = Form(
        ...,
        description="A JSON string representing the ManufacturingParameters.",
        example='{"quantity": 10, "base_material": "FR-4", ...}'
    )
):
    """
    This endpoint accepts a file upload and a form field containing a JSON string
    of manufacturing parameters. It returns a single ZIP archive containing:
    - `pcb_top.png`: The rendered top view of the board.
    - `pcb_bottom.png`: The rendered bottom view of the board.
    - `quote_details.json`: A file with the full quote, dimensions, and parameters received.
    """
    # 1. Validate the uploaded file type
    if not file.filename or not (file.filename.lower().endswith('.zip') or file.filename.lower().endswith('.rar')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP or RAR file.")

    # 2. Parse and normalize parameters using our new system
    try:
        raw_params = json.loads(params_json)
        params, warnings = ParameterNormalizer.validate_and_normalize(raw_params)
        
        # Log warnings if any
        if warnings:
            for warning in warnings:
                print(f"Parameter warning: {warning}")
                
    except json.JSONDecodeError as e:
        raise ParameterValidationError("params_json", params_json, "valid JSON string")
    except Exception as e:
        raise ParameterValidationError("parameters", str(e), "valid manufacturing parameters")

    archive_content = await file.read()

    # 3. Validate parameters before processing
    try:
        validation_result = RobustPricingService.validate_parameters(params)
        if not validation_result["is_valid"]:
            print(f"⚠️ Parameter validation warnings: {validation_result['warnings']}")
            print(f"❌ Parameter validation errors: {validation_result['errors']}")
    except Exception as e:
        print(f"⚠️ Parameter validation failed: {e}")
    
    # 4. Delegate all the core logic to the service layer with robust error handling and metrics
    try:
        with time_operation("quote_generation_total", {"material": params.base_material.value}):
            generator = QuoteGenerator(
                archive_content=archive_content,
                filename=file.filename,
                params=params
            )
            top_image_bytes, bottom_image_bytes, dimensions, quote = generator.process()
            
            # Record successful pricing request with new metrics
            metrics.record_pricing_request(params.base_material.value, "success", get_current_tenant() or "default")
        
        # Check if quote calculation succeeded
        if quote is None:
            print("⚠️ Quote calculation returned None, using fallback pricing")
            # Use robust pricing service as fallback
            if dimensions:
                fallback_result = RobustPricingService.calculate_robust_price(dimensions, params)
                quote = type('PriceQuote', (), {
                    'direct_cost_egp': fallback_result["details"].get("base_price_egp", 0),
                    'shipping_cost_egp': fallback_result["details"].get("shipping_cost_egp", 0),
                    'customs_rate_egp': fallback_result["details"].get("customs_rate_egp", 0),
                    'final_price_egp': fallback_result["final_price_egp"],
                    'currency': 'EGP',
                    'details': fallback_result["details"]
                })()
        
    except ValueError as e: # Catches specific, expected errors from our service
        print(f"❌ Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except PricingError as e:
        # Record pricing error
        PricingMetrics.record_pricing_error(e.code.value)
        raise  # Re-raise our custom error (will be handled by error handler)
        
    except Exception as e: # Catches any other unexpected server errors
        print(f"❌ Unexpected error occurred: {e}")
        PricingMetrics.record_pricing_error("internal_error")
        # Try to provide a fallback response instead of crashing
        try:
            if dimensions:
                fallback_result = RobustPricingService.calculate_robust_price(dimensions, params)
                quote = type('PriceQuote', (), {
                    'direct_cost_egp': fallback_result["details"].get("base_price_egp", 0),
                    'shipping_cost_egp': fallback_result["details"].get("shipping_cost_egp", 0),
                    'customs_rate_egp': fallback_result["details"].get("customs_rate_egp", 0),
                    'final_price_egp': fallback_result["final_price_egp"],
                    'currency': 'EGP',
                    'details': fallback_result["details"]
                })()
                print("✅ Fallback pricing applied successfully")
            else:
                raise HTTPException(status_code=500, detail="An internal server error occurred during processing.")
        except Exception as fallback_error:
            print(f"❌ Even fallback pricing failed: {fallback_error}")
            raise HTTPException(status_code=500, detail="An internal server error occurred during processing.")

    # 4. Construct the JSON data object using our clean Pydantic schema
    # This object will become the content of our .json file.
    response_data = GerberQuoteResponse(
        dimensions=dimensions,
        quote=quote,
        parameters_received=params,
    )

    # 5. Create the response ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
        # Add the rendered images
        zip_out.writestr("pcb_top.png", top_image_bytes)
        zip_out.writestr("pcb_bottom.png", bottom_image_bytes)
        
        # Add the structured JSON data file
        # .model_dump_json() is the correct method for Pydantic v2+
        zip_out.writestr(
            "quote_details.json",
            response_data.model_dump_json(indent=2)
        )

    # Prepare the buffer for reading
    zip_buffer.seek(0)
    
    # Create a safe, descriptive filename for the download
    original_filename = os.path.splitext(file.filename)[0]
    response_filename = f"quote_for_{original_filename}.zip"

    # 6. Stream the ZIP file back to the client
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={response_filename}"}
    )

@router.post(
    "/generate-quote-fast/",
    summary="Generate PCB Quote without Rendering Images",
    description="Upload a ZIP file and provide manufacturing options as a JSON string. Returns a JSON object with the quote details."
)
async def generate_quote_fast(
    file: UploadFile = File(..., description="A ZIP file containing Gerber layers."),
    params_json: str = Form(
        ...,
        description="A JSON string representing the ManufacturingParameters.",
        example='{"quantity": 10, "base_material": "FR-4", ...}'
    )
):
    """
    This endpoint accepts a file upload and a form field containing a JSON string
    of manufacturing parameters. It returns a JSON response containing:
    - `quote_details.json`: A file with the full quote, dimensions, and parameters received.
    """
    # 1. Validate the uploaded file type
    if not file.filename or not (file.filename.lower().endswith('.zip') or file.filename.lower().endswith('.rar')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP or RAR file.")

    # 2. Validate and parse the incoming JSON string into a Pydantic model
    try:
        params = ManufacturingParameters.model_validate_json(params_json)
    except ValidationError as e:
        # If validation fails, return a detailed 422 error
        raise HTTPException(status_code=422, detail=e.errors())

    archive_content = await file.read()

    # 3. Delegate all the core logic to the service layer
    try:
        generator = QuoteGenerator(
            archive_content=archive_content,
            filename=file.filename,
            params=params
        )
        dimensions, quote = generator.process_quote_only()
        
    except ValueError as e: # Catches specific, expected errors from our service
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e: # Catches any other unexpected server errors
        # In a real production app, you would log this error.
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred during processing.")

    # 4. Construct the JSON data object using our clean Pydantic schema
    # This object will become the content of our .json file.
    response_data = GerberQuoteResponse(
        dimensions=dimensions,
        quote=quote,
        parameters_received=params,
    )

    # 5. Return the JSON response
    return JSONResponse(content=response_data.model_dump())

@router.post(
    "/recalculate-price/",
    summary="Recalculate price based on new parameters",
    description="Recalculate the PCB quote based on dimensions and manufacturing parameters. Returns a JSON object with the quote details."
)
async def recalculate_price(
    dimensions: dict = Body(..., description="Board dimensions (width_mm, height_mm, area_m2)"),
    params: ManufacturingParameters = Body(..., description="Manufacturing parameters")
):
    """
    This endpoint recalculates the quote based on provided dimensions and manufacturing parameters.
    """
    try:
        # Validate parameters before recalculation
        validation_result = RobustPricingService.validate_parameters(params)
        if not validation_result["is_valid"]:
            print(f"⚠️ Parameter validation warnings: {validation_result['warnings']}")
            print(f"❌ Parameter validation errors: {validation_result['errors']}")
        
        calculator = PriceCalculator()
        quote = calculator.calculate_price(
            dimensions=type('BoardDimensions', (), dimensions)(),
            params=params
        )
    except ValueError as e:
        print(f"❌ Price recalculation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Unexpected error in price recalculation: {e}")
        # Try fallback pricing
        try:
            dimensions_obj = type('BoardDimensions', (), dimensions)()
            fallback_result = RobustPricingService.calculate_robust_price(dimensions_obj, params)
            quote = type('PriceQuote', (), {
                'direct_cost_egp': fallback_result["details"].get("base_price_egp", 0),
                'shipping_cost_egp': fallback_result["details"].get("shipping_cost_egp", 0),
                'customs_rate_egp': fallback_result["details"].get("customs_rate_egp", 0),
                'final_price_egp': fallback_result["final_price_egp"],
                'currency': 'EGP',
                'details': fallback_result["details"]
            })()
            print("✅ Fallback pricing applied for recalculation")
        except Exception as fallback_error:
            print(f"❌ Even fallback pricing failed: {fallback_error}")
            raise HTTPException(status_code=500, detail="An internal server error occurred during price recalculation.")

    response_data = GerberQuoteResponse(
        dimensions=dimensions,
        quote=quote,
        parameters_received=params,
    )
    return JSONResponse(content=response_data.model_dump())

@router.post(
    "/local-price/",
    summary="Calculate local FR-4 PCB price",
    description="Calculate local manufacturing price for FR-4 PCBs using local pricing rules"
)
async def calculate_local_price(
    dimensions: dict = Body(..., description="Board dimensions (width_mm, height_mm, area_m2)"),
    params: ManufacturingParameters = Body(..., description="Manufacturing parameters")
):
    """
    Calculate local FR-4 PCB manufacturing price based on local pricing rules.
    This endpoint uses the pricing structure from proto_tech2-main for local manufacturing.
    """
    import traceback
    
    try:
        # DEBUG: Log request parameters
        print(f"DEBUG: Received local-price request")
        print(f"DEBUG: Dimensions: {dimensions}")
        print(f"DEBUG: Params type: {type(params)}")
        print(f"DEBUG: Thickness type: {type(params.pcb_thickness_mm)}")
        print(f"DEBUG: Thickness value: {params.pcb_thickness_mm}")
        print(f"DEBUG: Tolerance value: {params.board_outline_tolerance}")
        
        # Normalize parameters using ParameterNormalizer to handle various formats
        normalizer = ParameterNormalizer()
        
        # Create normalized parameters object
        normalized_params = ManufacturingParameters(
            quantity=normalizer.normalize_quantity(params.quantity),
            base_material=normalizer.normalize_material(params.base_material),
            pcb_thickness_mm=normalizer.normalize_thickness(params.pcb_thickness_mm),
            board_outline_tolerance=normalizer.normalize_tolerance(params.board_outline_tolerance),
            min_via_hole_size_dia=normalizer.normalize_via_hole(params.min_via_hole_size_dia),
            pcb_color=params.pcb_color,
            surface_finish=params.surface_finish,
            confirm_production_file=params.confirm_production_file,
            electrical_test=params.electrical_test,
            via_covering=params.via_covering,
            outer_copper_weight=params.outer_copper_weight,
            delivery_format=params.delivery_format,
            different_designs=params.different_designs
        )
        
        print(f"DEBUG: Normalized tolerance: {normalized_params.board_outline_tolerance}")
        
        # Create BoardDimensions object from dict
        board_dimensions = type('BoardDimensions', (), dimensions)()
        
        # Calculate price using local pricing service with normalized parameters
        price_data = LocalPricingService.calculate_local_price(board_dimensions, normalized_params)
        
        print(f"DEBUG: Local price calculation successful")
        return JSONResponse(content=price_data)
        
    except TypeError as e:
        if "not supported between" in str(e):
            print(f"ERROR: Comparison error in local price calculation: {e}")
            print(f"ERROR: Full traceback:\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=500, 
                detail=f"Type comparison error: {str(e)}. This usually indicates an enum comparison issue."
            )
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        print(f"ERROR: Value error in local price calculation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"ERROR: Unexpected error in local price calculation: {e}")
        print(f"ERROR: Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"An internal server error occurred during price calculation: {str(e)}"
        )

@router.get(
    "/local-pricing-info/",
    summary="Get local FR-4 pricing information",
    description="Get detailed information about local FR-4 PCB pricing rules and multipliers"
)
async def get_local_pricing_info():
    """
    Get comprehensive information about local FR-4 PCB pricing rules.
    This includes all multipliers, thresholds, and pricing brackets.
    """
    try:
        pricing_info = LocalPricingService.get_pricing_info()
        return JSONResponse(content=pricing_info)
    except Exception as e:
        print(f"An unexpected error occurred while fetching pricing info: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching pricing information.")

@router.get(
    "/debug-enums/",
    summary="Debug endpoint to show expected enum values",
    description="Get all expected enum values for parameter validation debugging"
)
async def debug_enums():
    """Debug endpoint to show expected enum values for all parameters"""
    try:
        from app.schemas.pcb import (
            BoardOutlineTolerance, 
            PCBThickness, 
            BaseMaterial, 
            MinViaHole,
            SolderMaskColor,
            ViaCovering,
            CopperWeight,
            SurfaceFinish,
            DeliveryFormat
        )
        
        return JSONResponse(content={
            "board_outline_tolerance_values": [
                {"name": item.name, "value": item.value} 
                for item in BoardOutlineTolerance
            ],
            "pcb_thickness_values": [
                {"name": item.name, "value": item.value} 
                for item in PCBThickness
            ],
            "base_material_values": [
                {"name": item.name, "value": item.value} 
                for item in BaseMaterial
            ],
            "min_via_hole_values": [
                {"name": item.name, "value": item.value} 
                for item in MinViaHole
            ],
            "pcb_color_values": [
                {"name": item.name, "value": item.value} 
                for item in SolderMaskColor
            ],
            "via_covering_values": [
                {"name": item.name, "value": item.value} 
                for item in ViaCovering
            ],
            "copper_weight_values": [
                {"name": item.name, "value": item.value} 
                for item in CopperWeight
            ],
            "surface_finish_values": [
                {"name": item.name, "value": item.value} 
                for item in SurfaceFinish
            ],
            "delivery_format_values": [
                {"name": item.name, "value": item.value} 
                for item in DeliveryFormat
            ]
        })
    except Exception as e:
        print(f"Error in debug endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching enum values: {str(e)}")


# === IMAGE CACHE MANAGEMENT ENDPOINTS ===

@router.get(
    "/cache/stats/",
    summary="Get image cache statistics",
    description="Get statistics about the PCB image cache including number of entries and total size"
)
async def get_cache_stats():
    """
    Get statistics about the PCB image cache.
    """
    try:
        stats = image_cache.get_cache_stats()
        return JSONResponse(content=stats)
    except Exception as e:
        print(f"An unexpected error occurred while fetching cache stats: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching cache statistics.")


@router.post(
    "/cache/cleanup/",
    summary="Clean up expired cache entries",
    description="Remove expired cache entries to free up disk space"
)
async def cleanup_cache():
    """
    Clean up expired cache entries.
    """
    try:
        cleaned_count = image_cache.cleanup_expired_cache()
        return JSONResponse(content={
            "message": f"Successfully cleaned up {cleaned_count} expired cache entries",
            "cleaned_count": cleaned_count
        })
    except Exception as e:
        print(f"An unexpected error occurred during cache cleanup: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred during cache cleanup.")


# ===================================================================
#  NEW: Client-Side Recoloring Endpoints (Phase 1)
# ===================================================================

# Simple in-memory job storage (replace with Redis in production)
job_storage = {}

@router.post(
    "/quotes/v2",
    response_model=JobResponse,
    summary="Start async PCB quote generation (v2)",
    description="Start an async job to generate PCB artifacts for client-side recoloring. Returns job ID for status tracking."
)
async def create_quote_v2(
    file: UploadFile = File(..., description="A ZIP file containing Gerber layers."),
    params_json: str = Form(
        ...,
        description="A JSON string representing the ManufacturingParameters.",
        example='{"quantity": 10, "base_material": "FR-4", ...}'
    )
):
    """
    Start an async job to generate PCB artifacts for client-side recoloring.
    This endpoint returns immediately with a job ID, then processes in background.
    """
    import uuid
    import asyncio
    
    # Validate file type
    if not file.filename or not (file.filename.lower().endswith('.zip') or file.filename.lower().endswith('.rar')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP or RAR file.")

    # Validate parameters
    try:
        params = ManufacturingParameters.model_validate_json(params_json)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Store job status
    job_storage[job_id] = {
        "status": "queued",
        "progress": 0,
        "error": None,
        "manifest": None
    }
    
    # Start background processing (simplified version)
    asyncio.create_task(process_render_job_v2(job_id, file, params))
    
    return JobResponse(job_id=job_id, status="queued")

@router.get(
    "/quotes/{job_id}/manifest",
    response_model=QuoteManifest,
    summary="Get quote manifest with image URLs",
    description="Get the manifest containing all image URLs once the job completes."
)
async def get_quote_manifest(job_id: str):
    """Get manifest with image URLs once job completes"""
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_status = job_storage[job_id]
    
    if job_status["status"] == "completed":
        return QuoteManifest(**job_status["manifest"])
    elif job_status["status"] == "failed":
        raise HTTPException(status_code=500, detail=job_status.get("error", "Rendering failed"))
    else:
        raise HTTPException(status_code=202, detail=f"Job still {job_status['status']}")

@router.get(
    "/quotes/{job_id}/status",
    summary="Get job status (polling endpoint)",
    description="Get the current status of a rendering job."
)
async def get_job_status(job_id: str):
    """Get job status for polling"""
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(**job_storage[job_id])

@router.get(
    "/quotes/{job_id}/events",
    summary="Server-sent events for job progress",
    description="Stream job progress updates via Server-Sent Events."
)
async def quote_status_stream(job_id: str):
    """Server-sent events for job progress"""
    import asyncio
    
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def event_generator():
        while True:
            job_status = job_storage.get(job_id)
            if not job_status:
                break
                
            yield f"data: {json.dumps(job_status)}\n\n"
            
            if job_status["status"] in ["completed", "failed"]:
                break
                
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

# Background job processor (Phase 2 - Real Implementation)
async def process_render_job_v2(job_id: str, file: UploadFile, params: ManufacturingParameters):
    """Process rendering job in background with real base/mask generation"""
    try:
        import hashlib
        import tempfile
        
        # Update status to parsing
        job_storage[job_id]["status"] = "parsing"
        job_storage[job_id]["progress"] = 10
        
        # Read file content
        file_content = await file.read()
        file_hash = hashlib.md5(file_content).hexdigest()
        
        print(f"🔍 Processing job {job_id} for file {file.filename}")
        print(f"📁 File hash: {file_hash[:16]}...")
        
        # Update status to loading PCB
        job_storage[job_id]["status"] = "parsing"
        job_storage[job_id]["progress"] = 30
        
        # Create QuoteGenerator instance
        quote_gen = QuoteGenerator(file_content, file.filename, params)
        
        # Process the PCB (load and parse)
        with tempfile.TemporaryDirectory() as tmpdirname:
            quote_gen._extract_archive(tmpdirname)
            gerber_source_path = quote_gen._find_gerber_path(tmpdirname)
            quote_gen._rename_files_for_compatibility(gerber_source_path)
            quote_gen._load_pcb(gerber_source_path)
            
            # Update status to rendering
            job_storage[job_id]["status"] = "rendering"
            job_storage[job_id]["progress"] = 50
            
            # Generate base/mask artifacts
            print(f"🎨 Starting base/mask generation for job {job_id}")
            artifacts = quote_gen.generate_base_mask_artifacts(file_hash)
            
            # Update status to uploading
            job_storage[job_id]["status"] = "uploading"
            job_storage[job_id]["progress"] = 80
            
            # For now, store artifacts in memory (replace with S3 in production)
            # Create manifest with local URLs
            manifest = {"renderVersion": "v2", "sides": {}}
            
            for key, artifact in artifacts.items():
                side, variant, size = key.split('.')
                
                if side not in manifest["sides"]:
                    manifest["sides"][side] = {"base": {}, "mask": {}}
                
                # Create a data URL for the image (base64 encoded)
                import base64
                mime_type = "image/webp" if artifact['data'][:4] == b'RIFF' else "image/png"
                data_url = f"data:{mime_type};base64,{base64.b64encode(artifact['data']).decode()}"
                
                manifest["sides"][side][variant][size] = data_url
            
            # Update status to completed
            job_storage[job_id]["status"] = "completed"
            job_storage[job_id]["progress"] = 100
            job_storage[job_id]["manifest"] = manifest
            
            print(f"✅ Job {job_id} completed successfully with {len(artifacts)} artifacts")
            print(f"📊 Generated manifest with sides: {list(manifest['sides'].keys())}")
        
    except Exception as e:
        print(f"❌ Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()
        job_storage[job_id]["status"] = "failed"
        job_storage[job_id]["error"] = str(e)


# Unified Pricing Engine Endpoint
@router.post(
    "/calculate-price-unified/",
    summary="Calculate Price with Unified Engine",
    description="Calculate PCB pricing using the new unified pricing engine with A/B testing and advanced caching"
)
async def calculate_price_unified(
    params_json: str = Body(
        ...,
        description="Manufacturing parameters as JSON",
        example='{"quantity": 5, "base_material": "FR-4", "min_via_hole_size_dia": "0.3", "board_outline_tolerance": "±0.2mm (Regular)"}'
    ),
    dimensions_json: str = Body(
        ...,
        description="Board dimensions as JSON",
        example='{"width_mm": 50.0, "height_mm": 50.0}'
    )
):
    """Calculate price using the unified pricing engine with all Phase 4 features."""
    try:
        # Parse parameters
        raw_params = json.loads(params_json)
        params, warnings = ParameterNormalizer.validate_and_normalize(raw_params)
        
        # Parse dimensions
        dimensions_data = json.loads(dimensions_json)
        from app.schemas.pcb import BoardDimensions
        dimensions = BoardDimensions(
            width_mm=dimensions_data["width_mm"],
            height_mm=dimensions_data["height_mm"]
        )
        
        # Get tenant and user context
        tenant_id = get_current_tenant()
        user_id = None  # TODO: Get from auth context
        
        # Calculate price using unified engine
        result = await unified_pricing_engine.calculate_price(
            params, dimensions, tenant_id, user_id
        )
        
        # Record metrics
        metrics.record_pricing_request(
            params.base_material.value, 
            "success", 
            tenant_id or "default"
        )
        
        return JSONResponse(content={
            "success": True,
            "pricing_result": {
                "base_price": result.base_price,
                "final_price": result.final_price,
                "multipliers": result.multipliers,
                "breakdown": result.breakdown,
                "ab_test_variant": result.ab_test_variant,
                "engine_version": result.engine_version,
                "calculation_time_ms": result.calculation_time_ms,
                "from_cache": result.from_cache,
                "tenant_id": result.tenant_id
            },
            "parameters": params.model_dump(),
            "dimensions": dimensions.model_dump(),
            "tenant_context": get_tenant_context().to_dict() if get_tenant_context() else None,
            "warnings": warnings
        })
        
    except json.JSONDecodeError as e:
        metrics.record_pricing_error("INVALID_JSON", get_current_tenant() or "unknown")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        metrics.record_pricing_error("CALCULATION_FAILED", get_current_tenant() or "unknown")
        raise HTTPException(status_code=500, detail=f"Pricing calculation failed: {str(e)}")

@router.get(
    "/cache-stats/",
    summary="Get Cache Statistics",
    description="Get comprehensive cache statistics for the unified pricing engine"
)
async def get_cache_stats():
    """Get cache statistics for monitoring and optimization."""
    try:
        cache_stats = unified_pricing_engine.get_cache_stats()
        ab_test_status = unified_pricing_engine.get_ab_test_status()
        
        return JSONResponse(content={
            "cache_stats": cache_stats,
            "ab_testing": ab_test_status,
            "tenant_context": get_tenant_context().to_dict() if get_tenant_context() else None,
            "timestamp": time.time()
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

# Feature flag endpoints
@router.get(
    "/feature-flags/",
    summary="Get current feature flags",
    description="Get the current state of all feature flags for debugging and testing."
)
async def get_feature_flags():
    """Get all feature flags (for debugging)"""
    return JSONResponse(content={
        "flags": feature_flags.get_all_flags(),
        "client_side_recoloring": use_client_side_recoloring(),
        "message": "Use ?ff_pcb_client_recolor=true in URL to enable client-side recoloring"
    })

@router.post(
    "/feature-flags/{flag_name}",
    summary="Toggle a feature flag (testing only)",
    description="Enable or disable a feature flag for testing purposes."
)
async def toggle_feature_flag(flag_name: str, enabled: bool = Body(..., embed=True)):
    """Toggle a feature flag (for testing)"""
    if flag_name not in feature_flags.flags:
        raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")
    
    feature_flags.set_flag(flag_name, enabled)
    
    return JSONResponse(content={
        "flag": flag_name,
        "enabled": enabled,
        "message": f"Feature flag '{flag_name}' {'enabled' if enabled else 'disabled'}"
    })