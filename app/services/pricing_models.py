# app/services/pricing_models.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional

class PricingResultStatus(Enum):
    """Status of pricing calculation."""
    SUCCESS = "success"
    CACHED = "cached"
    FALLBACK = "fallback"
    ERROR = "error"

@dataclass
class Multipliers:
    """Container for all pricing multipliers."""
    material: float = 1.0
    quantity: float = 1.0
    thickness: float = 1.0
    copper_weight: float = 1.0
    via_hole: float = 1.0
    tolerance: float = 1.0
    color: float = 1.0
    surface_finish: float = 1.0
    silkscreen: float = 1.0
    high_spec: float = 1.0
    
    def total(self) -> float:
        """Calculate total multiplier."""
        return (self.material * self.quantity * self.thickness * 
                self.copper_weight * self.via_hole * self.tolerance * 
                self.color * self.surface_finish * self.silkscreen * 
                self.high_spec)

@dataclass
class PriceBreakdown:
    """Detailed breakdown of pricing components."""
    base_price_egp: float
    material_cost_egp: float
    quantity_cost_egp: float
    thickness_cost_egp: float
    copper_cost_egp: float
    via_hole_cost_egp: float
    tolerance_cost_egp: float
    color_cost_egp: float
    surface_finish_cost_egp: float
    engineering_fees_egp: float = 0.0
    shipping_cost_egp: float = 0.0
    customs_rate_egp: float = 0.0
    tax_amount_egp: float = 0.0
    
    @property
    def subtotal_egp(self) -> float:
        """Calculate subtotal before taxes and fees."""
        return (self.base_price_egp + self.material_cost_egp + 
                self.quantity_cost_egp + self.thickness_cost_egp + 
                self.copper_cost_egp + self.via_hole_cost_egp + 
                self.tolerance_cost_egp + self.color_cost_egp + 
                self.surface_finish_cost_egp)
    
    @property
    def total_egp(self) -> float:
        """Calculate final total price."""
        return (self.subtotal_egp + self.engineering_fees_egp + 
                self.shipping_cost_egp + self.customs_rate_egp + 
                self.tax_amount_egp)

@dataclass
class PriceResult:
    """Complete pricing result with metadata."""
    status: PricingResultStatus
    breakdown: PriceBreakdown
    multipliers: Multipliers
    calculation_time_ms: float
    from_cache: bool = False
    cache_key: Optional[str] = None
    warnings: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def final_price_egp(self) -> float:
        """Get final price for compatibility."""
        return self.breakdown.total_egp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "direct_cost_egp": self.breakdown.subtotal_egp,
            "shipping_cost_egp": self.breakdown.shipping_cost_egp,
            "customs_rate_egp": self.breakdown.customs_rate_egp,
            "final_price_egp": self.final_price_egp,
            "currency": "EGP",
            "details": {
                "base_price_egp": self.breakdown.base_price_egp,
                "material_cost_egp": self.breakdown.material_cost_egp,
                "quantity_cost_egp": self.breakdown.quantity_cost_egp,
                "thickness_cost_egp": self.breakdown.thickness_cost_egp,
                "copper_cost_egp": self.breakdown.copper_cost_egp,
                "via_hole_cost_egp": self.breakdown.via_hole_cost_egp,
                "tolerance_cost_egp": self.breakdown.tolerance_cost_egp,
                "color_cost_egp": self.breakdown.color_cost_egp,
                "surface_finish_cost_egp": self.breakdown.surface_finish_cost_egp,
                "engineering_fees_egp": self.breakdown.engineering_fees_egp,
                "tax_amount_egp": self.breakdown.tax_amount_egp,
                "multipliers": {
                    "material": self.multipliers.material,
                    "quantity": self.multipliers.quantity,
                    "thickness": self.multipliers.thickness,
                    "copper_weight": self.multipliers.copper_weight,
                    "via_hole": self.multipliers.via_hole,
                    "tolerance": self.multipliers.tolerance,
                    "color": self.multipliers.color,
                    "surface_finish": self.multipliers.surface_finish,
                    "silkscreen": self.multipliers.silkscreen,
                    "high_spec": self.multipliers.high_spec,
                    "total": self.multipliers.total()
                },
                "calculation_time_ms": self.calculation_time_ms,
                "from_cache": self.from_cache,
                "status": self.status.value
            }
        }
