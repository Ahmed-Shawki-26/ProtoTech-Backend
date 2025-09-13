# app/services/pricing_migration.py

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from app.schemas.pcb import ManufacturingParameters, BoardDimensions
from app.services.pricing_engine import pricing_engine
from app.services.pricing_models import PriceResult, PricingResultStatus, PriceBreakdown, Multipliers
from app.services.robust_pricing_service import RobustPricingService
from app.services.local_pricing_service import LocalPricingService
from app.core.feature_flags import feature_flags

logger = logging.getLogger(__name__)

class MigrationStrategy(Enum):
    """Migration strategy options."""
    OLD_ONLY = "old_only"           # Use only old pricing system
    NEW_ONLY = "new_only"           # Use only new pricing system
    NEW_WITH_FALLBACK = "new_with_fallback"  # Use new system with old fallback
    COMPARISON_MODE = "comparison_mode"       # Compare both systems
    GRADUAL_ROLLOUT = "gradual_rollout"       # Gradual percentage rollout

class PricingMigration:
    """
    Manages migration from old pricing system to new pricing engine.
    Provides gradual rollout and fallback mechanisms.
    """
    
    def __init__(self):
        self.strategy = MigrationStrategy.NEW_WITH_FALLBACK
        self.rollout_percentage = 0  # 0-100, percentage of requests to use new system
        self.comparison_mode = False
        self.fallback_enabled = True
        
        logger.info("PricingMigration initialized")
    
    def set_strategy(self, strategy: MigrationStrategy, rollout_percentage: int = 100):
        """
        Set migration strategy.
        
        Args:
            strategy: Migration strategy to use
            rollout_percentage: Percentage of requests to use new system (0-100)
        """
        self.strategy = strategy
        self.rollout_percentage = max(0, min(100, rollout_percentage))
        
        logger.info(f"Migration strategy set: {strategy.value}, rollout: {rollout_percentage}%")
    
    async def calculate_price(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        request_id: str = None
    ) -> PriceResult:
        """
        Calculate price using migration strategy.
        
        Args:
            params: Manufacturing parameters
            dimensions: Board dimensions
            request_id: Request ID for tracking
            
        Returns:
            PriceResult from appropriate pricing system
        """
        try:
            if self.strategy == MigrationStrategy.OLD_ONLY:
                return await self._calculate_with_old_system(params, dimensions)
            
            elif self.strategy == MigrationStrategy.NEW_ONLY:
                return await self._calculate_with_new_system(params, dimensions)
            
            elif self.strategy == MigrationStrategy.NEW_WITH_FALLBACK:
                return await self._calculate_with_new_and_fallback(params, dimensions, request_id)
            
            elif self.strategy == MigrationStrategy.COMPARISON_MODE:
                return await self._calculate_comparison_mode(params, dimensions)
            
            elif self.strategy == MigrationStrategy.GRADUAL_ROLLOUT:
                return await self._calculate_gradual_rollout(params, dimensions, request_id)
            
            else:
                logger.error(f"Unknown migration strategy: {self.strategy}")
                return await self._calculate_with_old_system(params, dimensions)
                
        except Exception as e:
            logger.error(f"Migration calculation failed: {e}")
            # Always fallback to old system on error
            return await self._calculate_with_old_system(params, dimensions)
    
    async def _calculate_with_old_system(
        self, 
        params: ManufacturingParameters, 
        dimensions: BoardDimensions
    ) -> PriceResult:
        """Calculate price using old pricing system."""
        try:
            logger.debug("Using old pricing system")
            
            # Use robust pricing service
            result = RobustPricingService.calculate_robust_price(dimensions, params)
            
            # Convert to new PriceResult format
            return self._convert_old_result_to_new(result, "old_system")
            
        except Exception as e:
            logger.error(f"Old pricing system failed: {e}")
            raise
    
    async def _calculate_with_new_system(
        self, 
        params: ManufacturingParameters, 
        dimensions: BoardDimensions
    ) -> PriceResult:
        """Calculate price using new pricing system."""
        try:
            logger.debug("Using new pricing system")
            
            return await pricing_engine.calculate_price(params, dimensions)
            
        except Exception as e:
            logger.error(f"New pricing system failed: {e}")
            raise
    
    async def _calculate_with_new_and_fallback(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        request_id: str = None
    ) -> PriceResult:
        """Calculate price with new system and old fallback."""
        try:
            # Try new system first
            try:
                result = await pricing_engine.calculate_price(params, dimensions)
                logger.debug(f"New pricing system succeeded for request {request_id}")
                return result
                
            except Exception as new_error:
                logger.warning(f"New pricing system failed, using fallback: {new_error}")
                
                if self.fallback_enabled:
                    # Use old system as fallback
                    old_result = await self._calculate_with_old_system(params, dimensions)
                    old_result.metadata["fallback_reason"] = str(new_error)
                    old_result.metadata["original_system"] = "new_with_fallback"
                    return old_result
                else:
                    # Re-raise the new system error
                    raise new_error
                    
        except Exception as e:
            logger.error(f"Both pricing systems failed: {e}")
            raise
    
    async def _calculate_comparison_mode(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions
    ) -> PriceResult:
        """Calculate price using both systems for comparison."""
        try:
            logger.debug("Using comparison mode")
            
            # Calculate with both systems
            new_result = await pricing_engine.calculate_price(params, dimensions)
            old_result = await self._calculate_with_old_system(params, dimensions)
            
            # Compare results
            price_diff = abs(new_result.final_price_egp - old_result.final_price_egp)
            price_diff_percent = (price_diff / old_result.final_price_egp) * 100
            
            # Add comparison metadata
            new_result.metadata["comparison_mode"] = True
            new_result.metadata["old_system_price"] = old_result.final_price_egp
            new_result.metadata["price_difference_egp"] = price_diff
            new_result.metadata["price_difference_percent"] = price_diff_percent
            
            if price_diff_percent > 10:  # More than 10% difference
                new_result.warnings.append(
                    f"Significant price difference: {price_diff_percent:.1f}% "
                    f"({price_diff:.2f} EGP)"
                )
            
            logger.info(f"Comparison: New={new_result.final_price_egp:.2f} EGP, "
                       f"Old={old_result.final_price_egp:.2f} EGP, "
                       f"Diff={price_diff_percent:.1f}%")
            
            # Return new system result with comparison data
            return new_result
            
        except Exception as e:
            logger.error(f"Comparison mode failed: {e}")
            raise
    
    async def _calculate_gradual_rollout(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        request_id: str = None
    ) -> PriceResult:
        """Calculate price with gradual rollout."""
        try:
            # Use request ID or hash of parameters to determine which system to use
            if request_id:
                # Use request ID to determine rollout
                hash_value = hash(request_id) % 100
            else:
                # Use parameter hash
                hash_value = hash(str(params.model_dump())) % 100
            
            if hash_value < self.rollout_percentage:
                # Use new system
                logger.debug(f"Gradual rollout: Using new system (hash: {hash_value})")
                result = await pricing_engine.calculate_price(params, dimensions)
                result.metadata["rollout_system"] = "new"
                result.metadata["rollout_hash"] = hash_value
                return result
            else:
                # Use old system
                logger.debug(f"Gradual rollout: Using old system (hash: {hash_value})")
                result = await self._calculate_with_old_system(params, dimensions)
                result.metadata["rollout_system"] = "old"
                result.metadata["rollout_hash"] = hash_value
                return result
                
        except Exception as e:
            logger.error(f"Gradual rollout failed: {e}")
            raise
    
    def _convert_old_result_to_new(self, old_result: Dict[str, Any], system: str) -> PriceResult:
        """Convert old pricing result to new PriceResult format."""
        try:
            from app.services.pricing_models import (
                PriceResult, PriceBreakdown, Multipliers, PricingResultStatus
            )
            
            # Extract data from old result
            final_price = old_result.get("final_price_egp", 0.0)
            direct_cost = old_result.get("direct_cost_egp", 0.0)
            shipping_cost = old_result.get("shipping_cost_egp", 0.0)
            customs_rate = old_result.get("customs_rate_egp", 0.0)
            
            # Create breakdown
            breakdown = PriceBreakdown(
                base_price_egp=direct_cost,
                material_cost_egp=0.0,
                quantity_cost_egp=0.0,
                thickness_cost_egp=0.0,
                copper_cost_egp=0.0,
                via_hole_cost_egp=0.0,
                tolerance_cost_egp=0.0,
                color_cost_egp=0.0,
                surface_finish_cost_egp=0.0,
                engineering_fees_egp=0.0,
                shipping_cost_egp=shipping_cost,
                customs_rate_egp=customs_rate,
                tax_amount_egp=final_price - direct_cost - shipping_cost - customs_rate
            )
            
            # Create result
            result = PriceResult(
                status=PricingResultStatus.SUCCESS,
                breakdown=breakdown,
                multipliers=Multipliers(),
                calculation_time_ms=0.0,
                from_cache=False,
                metadata={"original_system": system}
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to convert old result to new format: {e}")
            # Return minimal result
            from app.services.pricing_models import (
                PriceResult, PriceBreakdown, Multipliers, PricingResultStatus
            )
            
            breakdown = PriceBreakdown(
                base_price_egp=old_result.get("final_price_egp", 0.0),
                shipping_cost_egp=0.0,
                customs_rate_egp=0.0,
                tax_amount_egp=0.0
            )
            
            return PriceResult(
                status=PricingResultStatus.FALLBACK,
                breakdown=breakdown,
                multipliers=Multipliers(),
                calculation_time_ms=0.0,
                metadata={"original_system": system, "conversion_error": str(e)}
            )
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        return {
            "strategy": self.strategy.value,
            "rollout_percentage": self.rollout_percentage,
            "comparison_mode": self.comparison_mode,
            "fallback_enabled": self.fallback_enabled,
            "feature_flags": {
                "client_side_recoloring": feature_flags.is_enabled("pcb_client_recolor"),
                "async_quote_generation": feature_flags.is_enabled("async_quote_generation")
            }
        }
    
    def update_rollout_percentage(self, percentage: int):
        """Update rollout percentage."""
        self.rollout_percentage = max(0, min(100, percentage))
        logger.info(f"Rollout percentage updated to {self.rollout_percentage}%")
    
    def enable_comparison_mode(self, enabled: bool = True):
        """Enable or disable comparison mode."""
        self.comparison_mode = enabled
        if enabled:
            self.strategy = MigrationStrategy.COMPARISON_MODE
        logger.info(f"Comparison mode {'enabled' if enabled else 'disabled'}")

# Global pricing migration instance
pricing_migration = PricingMigration()
