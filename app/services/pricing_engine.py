# app/services/pricing_engine.py

import time
import logging
from typing import Dict, Any, Optional, Tuple

from app.schemas.pcb import ManufacturingParameters, BoardDimensions
from app.services.parameter_normalizer import ParameterNormalizer
from app.services.parameter_validator import ParameterValidator
from app.services.pricing_rules_engine import PricingRulesEngine
from app.services.pricing_cache import PricingCache
from app.services.price_calculator_new import PriceCalculator
from app.services.pricing_models import (
    PricingResultStatus, Multipliers, PriceBreakdown, PriceResult
)
from app.core.exceptions import PricingError, ErrorCode, raise_pricing_error
from app.core.metrics import PricingMetrics, time_operation

logger = logging.getLogger(__name__)

class PricingEngine:
    """
    Unified pricing engine with clean architecture.
    Single entry point for all pricing calculations.
    """
    
    def __init__(self):
        self.rules_engine = PricingRulesEngine()
        self.validator = ParameterValidator()
        self.cache = PricingCache()
        self.calculator = PriceCalculator()
        
        logger.info("PricingEngine initialized with all components")
    
    async def calculate_price(
        self, 
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        use_cache: bool = True
    ) -> PriceResult:
        """
        Calculate price with full pipeline.
        
        Args:
            params: Manufacturing parameters
            dimensions: Board dimensions
            use_cache: Whether to use caching
            
        Returns:
            PriceResult with complete pricing information
        """
        start_time = time.time()
        
        try:
            # 1. Validate and normalize parameters
            normalized_params = self.validator.normalize(params)
            validation_result = self.validator.validate_dimensions(dimensions)
            if not validation_result.is_valid:
                raise_pricing_error("Invalid board dimensions", context={"errors": validation_result.errors})
            
            # 2. Generate cache key
            cache_key = self._generate_cache_key(normalized_params, dimensions) if use_cache else None
            
            # 3. Check cache
            if use_cache and cache_key:
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    PricingMetrics.record_cache_hit("memory")
                    return cached_result
            
            # 4. Calculate multipliers using rules engine
            multipliers = self.rules_engine.calculate_multipliers(normalized_params)
            
            # 5. Calculate base price
            base_price = self.calculator.calculate_base_price(dimensions, normalized_params)
            
            # 6. Build price breakdown
            breakdown = self._build_price_breakdown(base_price, multipliers, normalized_params)
            
            # 7. Create result
            calculation_time = (time.time() - start_time) * 1000  # Convert to ms
            result = PriceResult(
                status=PricingResultStatus.SUCCESS,
                breakdown=breakdown,
                multipliers=multipliers,
                calculation_time_ms=calculation_time,
                from_cache=False,
                cache_key=cache_key
            )
            
            # 8. Cache result
            if use_cache and cache_key:
                await self.cache.set(cache_key, result)
            
            # 9. Record metrics
            PricingMetrics.record_pricing_request(normalized_params.base_material.value, "success")
            PricingMetrics.record_pricing_duration("calculate_price", calculation_time / 1000)
            
            logger.info(f"Price calculated successfully: {result.final_price_egp:.2f} EGP in {calculation_time:.2f}ms")
            return result
            
        except Exception as e:
            calculation_time = (time.time() - start_time) * 1000
            logger.error(f"Pricing calculation failed: {e}")
            PricingMetrics.record_pricing_error("calculation_failed")
            
            # Try fallback calculation
            try:
                fallback_result = await self._fallback_calculation(params, dimensions)
                fallback_result.status = PricingResultStatus.FALLBACK
                fallback_result.calculation_time_ms = calculation_time
                return fallback_result
            except Exception as fallback_error:
                logger.error(f"Fallback calculation also failed: {fallback_error}")
                raise_pricing_error(
                    f"Pricing calculation failed: {str(e)}",
                    technical_details=str(fallback_error)
                )
    
    def _generate_cache_key(self, params: ManufacturingParameters, dimensions: BoardDimensions) -> str:
        """Generate deterministic cache key."""
        import hashlib
        import json
        
        # Create normalized data structure
        key_data = {
            "params": {
                "quantity": params.quantity,
                "base_material": params.base_material.value,
                "thickness": getattr(params, 'pcb_thickness_mm', '1.6'),
                "copper_weight": getattr(params, 'outer_copper_weight', '1 oz'),
                "via_hole": params.min_via_hole_size_dia.value,
                "tolerance": params.board_outline_tolerance.value,
                "color": getattr(params, 'pcb_color', 'Green'),
                "surface_finish": getattr(params, 'surface_finish', 'Immersed Tin')
            },
            "dimensions": {
                "width_mm": dimensions.width_mm,
                "height_mm": dimensions.height_mm,
                "area_m2": dimensions.area_m2
            }
        }
        
        # Create hash
        key_string = json.dumps(key_data, sort_keys=True)
        return f"price:v2:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def _build_price_breakdown(
        self, 
        base_price: float, 
        multipliers: Multipliers,
        params: ManufacturingParameters
    ) -> PriceBreakdown:
        """Build detailed price breakdown."""
        
        # Calculate individual costs
        material_cost = base_price * (multipliers.material - 1.0)
        quantity_cost = base_price * (multipliers.quantity - 1.0)
        thickness_cost = base_price * (multipliers.thickness - 1.0)
        copper_cost = base_price * (multipliers.copper_weight - 1.0)
        via_hole_cost = base_price * (multipliers.via_hole - 1.0)
        tolerance_cost = base_price * (multipliers.tolerance - 1.0)
        color_cost = base_price * (multipliers.color - 1.0)
        surface_finish_cost = base_price * (multipliers.surface_finish - 1.0)
        
        # Calculate fees (these could be made configurable)
        engineering_fees = base_price * 0.05 if params.quantity < 10 else 0.0  # 5% for small quantities
        shipping_cost = 45.0  # Fixed shipping cost
        customs_rate = base_price * 0.05  # 5% customs
        tax_amount = (base_price + material_cost + quantity_cost + thickness_cost + 
                     copper_cost + via_hole_cost + tolerance_cost + color_cost + 
                     surface_finish_cost + engineering_fees) * 0.14  # 14% VAT
        
        return PriceBreakdown(
            base_price_egp=base_price,
            material_cost_egp=material_cost,
            quantity_cost_egp=quantity_cost,
            thickness_cost_egp=thickness_cost,
            copper_cost_egp=copper_cost,
            via_hole_cost_egp=via_hole_cost,
            tolerance_cost_egp=tolerance_cost,
            color_cost_egp=color_cost,
            surface_finish_cost_egp=surface_finish_cost,
            engineering_fees_egp=engineering_fees,
            shipping_cost_egp=shipping_cost,
            customs_rate_egp=customs_rate,
            tax_amount_egp=tax_amount
        )
    
    async def _fallback_calculation(
        self, 
        params: ManufacturingParameters, 
        dimensions: BoardDimensions
    ) -> PriceResult:
        """Fallback calculation using simplified rules."""
        logger.warning("Using fallback pricing calculation")
        
        # Simple fallback: base price * material multiplier
        base_price = dimensions.area_m2 * 10000 * 1.5  # 1.5 EGP per cm²
        
        # Simple material multipliers
        material_multipliers = {
            "FR-4": 1.0,
            "Flex": 2.5,
            "Aluminum": 3.0,
            "Copper Core": 2.8,
            "Rogers": 4.0,
            "PTFE": 5.0
        }
        
        material_mult = material_multipliers.get(params.base_material.value, 1.0)
        quantity_mult = 2.0 if params.quantity == 1 else 1.0
        
        final_price = base_price * material_mult * quantity_mult
        
        # Create simple breakdown
        breakdown = PriceBreakdown(
            base_price_egp=base_price,
            material_cost_egp=base_price * (material_mult - 1.0),
            quantity_cost_egp=base_price * (quantity_mult - 1.0),
            thickness_cost_egp=0.0,
            copper_cost_egp=0.0,
            via_hole_cost_egp=0.0,
            tolerance_cost_egp=0.0,
            color_cost_egp=0.0,
            surface_finish_cost_egp=0.0,
            engineering_fees_egp=45.0,
            shipping_cost_egp=45.0,
            customs_rate_egp=final_price * 0.05,
            tax_amount_egp=final_price * 0.14
        )
        
        multipliers = Multipliers(material=material_mult, quantity=quantity_mult)
        
        return PriceResult(
            status=PricingResultStatus.FALLBACK,
            breakdown=breakdown,
            multipliers=multipliers,
            calculation_time_ms=0.0,
            warnings=["Fallback calculation used"]
        )

# Global pricing engine instance
pricing_engine = PricingEngine()
