# app/services/tenant_aware_pricing_engine.py

from typing import Dict, Any, Optional, List
import logging
from dataclasses import dataclass
import asyncio

from app.core.tenant_context import get_current_tenant, get_tenant_context, require_tenant
from app.core.feature_flags import feature_flags, is_feature_enabled
from app.core.monitoring.metrics import metrics, time_operation
from app.core.exceptions import PricingError, ErrorCode
from app.services.pricing_rules_engine import PricingRulesEngine, PricingConfig
from app.services.price_calculator import PriceCalculator
from app.schemas.pcb import ManufacturingParameters, BoardDimensions

logger = logging.getLogger(__name__)

@dataclass
class TenantPricingConfig:
    """Tenant-specific pricing configuration."""
    tenant_id: str
    material_multipliers: Dict[str, float]
    quantity_brackets: List[tuple]
    custom_rules: Dict[str, Any]
    discount_percentage: float = 0.0
    markup_percentage: float = 0.0

class TenantAwarePricingEngine:
    """Pricing engine with tenant isolation and customization."""
    
    def __init__(self):
        self.base_rules_engine = PricingRulesEngine()
        self.price_calculator = PriceCalculator()
        self.tenant_configs: Dict[str, TenantPricingConfig] = {}
        self._load_tenant_configs()
    
    def _load_tenant_configs(self):
        """Load tenant-specific pricing configurations."""
        # Default tenant configurations
        default_config = TenantPricingConfig(
            tenant_id="default",
            material_multipliers={
                "FR-4": 1.0,
                "Flex": 2.5,
                "Aluminum": 3.0,
                "Copper Core": 2.8,
                "Rogers": 4.0,
                "PTFE": 5.0
            },
            quantity_brackets=[
                (1, 2.0),
                (3, 1.5),
                (5, 1.0),
                (10, 0.9),
                (50, 0.8),
                (100, 0.7),
            ],
            custom_rules={}
        )
        
        # Enterprise tenant with discounts
        enterprise_config = TenantPricingConfig(
            tenant_id="enterprise",
            material_multipliers={
                "FR-4": 0.9,  # 10% discount
                "Flex": 2.25,  # 10% discount
                "Aluminum": 2.7,  # 10% discount
                "Copper Core": 2.52,  # 10% discount
                "Rogers": 3.6,  # 10% discount
                "PTFE": 4.5,  # 10% discount
            },
            quantity_brackets=[
                (1, 1.8),    # Better pricing for enterprise
                (3, 1.35),
                (5, 0.9),
                (10, 0.8),
                (50, 0.7),
                (100, 0.6),
            ],
            custom_rules={
                "volume_discount": True,
                "priority_support": True
            },
            discount_percentage=10.0
        )
        
        # Partner tenant with special pricing
        partner_config = TenantPricingConfig(
            tenant_id="partner",
            material_multipliers={
                "FR-4": 0.85,  # 15% discount
                "Flex": 2.125,  # 15% discount
                "Aluminum": 2.55,  # 15% discount
                "Copper Core": 2.38,  # 15% discount
                "Rogers": 3.4,  # 15% discount
                "PTFE": 4.25,  # 15% discount
            },
            quantity_brackets=[
                (1, 1.7),    # Even better pricing for partners
                (3, 1.275),
                (5, 0.85),
                (10, 0.75),
                (50, 0.65),
                (100, 0.55),
            ],
            custom_rules={
                "volume_discount": True,
                "priority_support": True,
                "white_label": True
            },
            discount_percentage=15.0
        )
        
        self.tenant_configs = {
            "default": default_config,
            "enterprise": enterprise_config,
            "partner": partner_config
        }
        
        logger.info(f"Loaded {len(self.tenant_configs)} tenant pricing configurations")
    
    def get_tenant_config(self, tenant_id: str) -> TenantPricingConfig:
        """Get pricing configuration for a tenant."""
        return self.tenant_configs.get(tenant_id, self.tenant_configs["default"])
    
    def create_tenant_rules_engine(self, tenant_id: str) -> PricingRulesEngine:
        """Create a pricing rules engine for a specific tenant."""
        tenant_config = self.get_tenant_config(tenant_id)
        
        # Create tenant-specific pricing config
        pricing_config = PricingConfig(
            material_multipliers=tenant_config.material_multipliers,
            quantity_brackets=tenant_config.quantity_brackets,
            # Use base config for other settings
            thickness_multipliers=self.base_rules_engine.config.thickness_multipliers,
            copper_weight_multipliers=self.base_rules_engine.config.copper_weight_multipliers,
            via_hole_multipliers=self.base_rules_engine.config.via_hole_multipliers,
            tolerance_multipliers=self.base_rules_engine.config.tolerance_multipliers,
            color_multipliers=self.base_rules_engine.config.color_multipliers,
            surface_finish_multipliers=self.base_rules_engine.config.surface_finish_multipliers,
            silkscreen_multipliers=self.base_rules_engine.config.silkscreen_multipliers,
            high_spec_multipliers=self.base_rules_engine.config.high_spec_multipliers,
            panel_area_pricing=self.base_rules_engine.config.panel_area_pricing
        )
        
        return PricingRulesEngine(pricing_config)
    
    @time_operation("tenant_aware_pricing")
    async def calculate_price(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate price with tenant awareness."""
        try:
            # Get tenant context
            if not tenant_id:
                tenant_id = get_current_tenant() or "default"
            
            # Check if new pricing engine is enabled for this tenant
            use_new_engine = is_feature_enabled("new_pricing_engine", tenant_id=tenant_id)
            
            if use_new_engine:
                return await self._calculate_with_new_engine(params, dimensions, tenant_id)
            else:
                return await self._calculate_with_legacy_engine(params, dimensions, tenant_id)
                
        except Exception as e:
            logger.error(f"Error in tenant-aware pricing calculation: {e}")
            metrics.record_pricing_error("CALCULATION_FAILED", tenant_id or "unknown")
            raise PricingError(
                code=ErrorCode.PRICING_CALCULATION_FAILED,
                user_message="Failed to calculate pricing",
                technical_details=str(e),
                context={"tenant_id": tenant_id}
            )
    
    async def _calculate_with_new_engine(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Calculate price using the new engine."""
        # Create tenant-specific rules engine
        rules_engine = self.create_tenant_rules_engine(tenant_id)
        
        # Calculate multipliers
        multipliers = rules_engine.calculate_multipliers(params)
        
        # Calculate base price
        base_price = self.price_calculator.calculate_base_price(dimensions, params)
        
        # Apply tenant-specific adjustments
        tenant_config = self.get_tenant_config(tenant_id)
        
        # Calculate final price with tenant adjustments
        total_multiplier = multipliers.total()
        final_price = base_price * total_multiplier
        
        # Apply tenant discount/markup
        if tenant_config.discount_percentage > 0:
            final_price *= (1 - tenant_config.discount_percentage / 100)
        elif tenant_config.markup_percentage > 0:
            final_price *= (1 + tenant_config.markup_percentage / 100)
        
        # Record metrics
        metrics.record_pricing_request(
            material=params.base_material.value,
            status="success",
            tenant_id=tenant_id
        )
        
        return {
            "base_price": base_price,
            "multipliers": {
                "material": multipliers.material,
                "quantity": multipliers.quantity,
                "thickness": multipliers.thickness,
                "copper_weight": multipliers.copper_weight,
                "via_hole": multipliers.via_hole,
                "tolerance": multipliers.tolerance,
                "color": multipliers.color,
                "surface_finish": multipliers.surface_finish,
                "silkscreen": multipliers.silkscreen,
                "high_spec": multipliers.high_spec,
                "total": total_multiplier
            },
            "final_price": final_price,
            "tenant_adjustments": {
                "discount_percentage": tenant_config.discount_percentage,
                "markup_percentage": tenant_config.markup_percentage,
                "tenant_id": tenant_id
            },
            "engine_version": "2.0.0",
            "from_cache": False
        }
    
    async def _calculate_with_legacy_engine(
        self,
        params: ManufacturingParameters,
        dimensions: BoardDimensions,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Calculate price using the legacy engine."""
        # Use base rules engine for legacy calculations
        multipliers = self.base_rules_engine.calculate_multipliers(params)
        base_price = self.price_calculator.calculate_base_price(dimensions, params)
        
        # Apply basic tenant adjustments
        tenant_config = self.get_tenant_config(tenant_id)
        total_multiplier = multipliers.total()
        final_price = base_price * total_multiplier
        
        # Apply tenant discount/markup
        if tenant_config.discount_percentage > 0:
            final_price *= (1 - tenant_config.discount_percentage / 100)
        elif tenant_config.markup_percentage > 0:
            final_price *= (1 + tenant_config.markup_percentage / 100)
        
        # Record metrics
        metrics.record_pricing_request(
            material=params.base_material.value,
            status="success",
            tenant_id=tenant_id
        )
        
        return {
            "base_price": base_price,
            "multipliers": {
                "material": multipliers.material,
                "quantity": multipliers.quantity,
                "thickness": multipliers.thickness,
                "copper_weight": multipliers.copper_weight,
                "via_hole": multipliers.via_hole,
                "tolerance": multipliers.tolerance,
                "color": multipliers.color,
                "surface_finish": multipliers.surface_finish,
                "silkscreen": multipliers.silkscreen,
                "high_spec": multipliers.high_spec,
                "total": total_multiplier
            },
            "final_price": final_price,
            "tenant_adjustments": {
                "discount_percentage": tenant_config.discount_percentage,
                "markup_percentage": tenant_config.markup_percentage,
                "tenant_id": tenant_id
            },
            "engine_version": "1.0.0",
            "from_cache": False
        }
    
    def update_tenant_config(self, tenant_id: str, config: TenantPricingConfig):
        """Update pricing configuration for a tenant."""
        self.tenant_configs[tenant_id] = config
        logger.info(f"Updated pricing configuration for tenant: {tenant_id}")
    
    def get_tenant_pricing_info(self, tenant_id: str) -> Dict[str, Any]:
        """Get pricing information for a tenant."""
        tenant_config = self.get_tenant_config(tenant_id)
        
        return {
            "tenant_id": tenant_id,
            "material_multipliers": tenant_config.material_multipliers,
            "quantity_brackets": tenant_config.quantity_brackets,
            "discount_percentage": tenant_config.discount_percentage,
            "markup_percentage": tenant_config.markup_percentage,
            "custom_rules": tenant_config.custom_rules,
            "engine_version": "2.0.0" if is_feature_enabled("new_pricing_engine", tenant_id=tenant_id) else "1.0.0"
        }
    
    def get_all_tenant_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all tenant configurations."""
        return {
            tenant_id: self.get_tenant_pricing_info(tenant_id)
            for tenant_id in self.tenant_configs.keys()
        }

# Global tenant-aware pricing engine instance
tenant_aware_pricing_engine = TenantAwarePricingEngine()
