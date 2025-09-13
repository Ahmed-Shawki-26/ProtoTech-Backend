# app/services/pricing_rules_engine.py

import logging
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from app.schemas.pcb import ManufacturingParameters, BaseMaterial, MinViaHole, BoardOutlineTolerance
from app.services.pricing_models import Multipliers
from app.utils.enum_helpers import get_thickness_value

logger = logging.getLogger(__name__)

@dataclass
class PricingConfig:
    """Configuration for pricing rules."""
    
    # Material multipliers
    material_multipliers: Dict[str, float] = None
    
    # Quantity brackets: (min_quantity, multiplier)
    quantity_brackets: List[Tuple[int, float]] = None
    
    # Thickness multipliers
    thickness_multipliers: Dict[str, float] = None
    
    # Copper weight multipliers
    copper_weight_multipliers: Dict[str, float] = None
    
    # Via hole multipliers
    via_hole_multipliers: Dict[float, float] = None
    
    # Tolerance multipliers
    tolerance_multipliers: Dict[str, float] = None
    
    # Color multipliers
    color_multipliers: Dict[str, float] = None
    
    # Surface finish multipliers
    surface_finish_multipliers: Dict[str, float] = None
    
    # Silkscreen multipliers
    silkscreen_multipliers: Dict[str, float] = None
    
    # High specification multipliers
    high_spec_multipliers: Dict[str, Dict[str, float]] = None
    
    # Panel area pricing (material-specific)
    panel_area_pricing: Dict[str, Dict[str, float]] = None
    
    def __post_init__(self):
        """Set default values if not provided."""
        if self.material_multipliers is None:
            self.material_multipliers = {
                "FR-4": 1.0,
                "Flex": 2.5,
                "Aluminum": 3.0,
                "Copper Core": 2.8,
                "Rogers": 4.0,
                "PTFE": 5.0
            }
        
        if self.quantity_brackets is None:
            self.quantity_brackets = [
                (1, 2.0),    # 1 piece: 2x multiplier
                (3, 1.5),    # 3 pieces: 1.5x
                (5, 1.0),    # 5+ pieces: 1x
                (10, 0.9),   # 10+ pieces: 0.9x
                (50, 0.8),   # 50+ pieces: 0.8x
                (100, 0.7),  # 100+ pieces: 0.7x
            ]
        
        if self.thickness_multipliers is None:
            self.thickness_multipliers = {
                "0.8": 1.2,
                "1.0": 1.1,
                "1.2": 1.05,
                "1.6": 1.0,
                "2.0": 1.1,
                "2.4": 1.2,
            }
        
        if self.copper_weight_multipliers is None:
            self.copper_weight_multipliers = {
                "1/3 oz": 0.9,
                "1 oz": 1.0,
                "2 oz": 1.3,
                "3 oz": 1.6,
            }
        
        if self.via_hole_multipliers is None:
            self.via_hole_multipliers = {
                0.3: 1.0,
                0.25: 1.1,
                0.2: 1.3,
                0.15: 1.6,
            }
        
        if self.tolerance_multipliers is None:
            self.tolerance_multipliers = {
                "±0.2mm (Regular)": 1.0,
                "±0.1mm (Precision)": 1.2,
            }
        
        if self.color_multipliers is None:
            self.color_multipliers = {
                "Green": 1.0,
                "Blue": 1.05,
                "Red": 1.1,
                "Black": 1.15,
                "White": 1.2,
                "Yellow": 1.25,
            }
        
        if self.surface_finish_multipliers is None:
            self.surface_finish_multipliers = {
                "HASL": 1.05,
                "ENIG": 1.3,
                "immersion tin": 1.0,
            }
        
        if self.silkscreen_multipliers is None:
            self.silkscreen_multipliers = {
                "white": 1.0,
                "black": 1.05,
            }
        
        if self.high_spec_multipliers is None:
            self.high_spec_multipliers = {
                "impedance_control": {"no": 1.0, "yes": 1.2},
                "gold_fingers": {"no": 1.0, "yes": 1.3},
                "stencil": {"no": 1.0, "yes": 1.1},
                "mark_on_pcb": {"no": 1.0, "yes": 1.05},
                "confirm_production_file": {"no": 1.0, "yes": 1.1},
                "electrical_test": {"flying probe": 1.2, "optical manual inspection": 1.0}
            }
        
        if self.panel_area_pricing is None:
            self.panel_area_pricing = {
                "FR-4": {
                    "≤1000": 1.6,
                    "1001-1500": 1.5,
                    "1501-2000": 1.4,
                    "2001-2500": 1.3,
                    "2501-3000": 1.2,
                    "min_price": 1.2
                }
            }

class PricingRulesEngine:
    """
    Manages all pricing rules and multiplier calculations.
    Centralized location for all pricing logic.
    """
    
    def __init__(self, config: PricingConfig = None):
        self.config = config or PricingConfig()
        self._compile_rules()
        logger.info("PricingRulesEngine initialized")
    
    def _compile_rules(self):
        """Pre-compile rules for better performance."""
        # Create efficient lookup functions
        self.quantity_func = self._create_bracket_function(self.config.quantity_brackets)
        logger.debug("Rules compiled successfully")
    
    @staticmethod
    def _create_bracket_function(brackets: List[Tuple[int, float]]):
        """Create efficient bracket lookup function."""
        def bracket_func(value: int) -> float:
            # Sort brackets by quantity (descending) for efficient lookup
            for threshold, multiplier in sorted(brackets, key=lambda x: x[0], reverse=True):
                if value >= threshold:
                    return multiplier
            # Return the highest multiplier if below all thresholds
            return max(multiplier for _, multiplier in brackets)
        return bracket_func
    
    def calculate_multipliers(self, params: ManufacturingParameters) -> Multipliers:
        """
        Calculate all pricing multipliers based on parameters.
        
        Args:
            params: Manufacturing parameters
            
        Returns:
            Multipliers object with all calculated multipliers
        """
        try:
            multipliers = Multipliers()
            
            # Material multiplier
            material_key = params.base_material.value
            multipliers.material = self.config.material_multipliers.get(material_key, 1.0)
            
            # Quantity multiplier
            multipliers.quantity = self.quantity_func(params.quantity)
            
            # Thickness multiplier - using safe enum conversion
            thickness = getattr(params, 'pcb_thickness_mm', '1.6')
            thickness_value = get_thickness_value(thickness)
            multipliers.thickness = self.config.thickness_multipliers.get(str(thickness_value), 1.0)
            
            # Copper weight multiplier
            copper_weight = getattr(params, 'outer_copper_weight', '1 oz')
            multipliers.copper_weight = self.config.copper_weight_multipliers.get(copper_weight, 1.0)
            
            # Via hole multiplier
            via_hole_str = params.min_via_hole_size_dia.value  
            multipliers.via_hole = self.config.via_hole_multipliers.get(via_hole_str, 1.0)
            
            # Tolerance multiplier
            tolerance = params.board_outline_tolerance.value
            multipliers.tolerance = self.config.tolerance_multipliers.get(tolerance, 1.0)
            
            # Color multiplier (convert to lowercase for consistency)
            color = getattr(params, 'pcb_color', 'green')
            if isinstance(color, str):
                color = color.lower()
            multipliers.color = self.config.color_multipliers.get(color, 1.0)
            
            # Surface finish multiplier
            surface_finish = getattr(params, 'surface_finish', 'HASL')
            if isinstance(surface_finish, str):
                surface_finish = surface_finish.lower()
            multipliers.surface_finish = self.config.surface_finish_multipliers.get(surface_finish, 1.0)
            
            # Silkscreen multiplier
            silkscreen = getattr(params, 'silkscreen', 'white')
            if isinstance(silkscreen, str):
                silkscreen = silkscreen.lower()
            multipliers.silkscreen = self.config.silkscreen_multipliers.get(silkscreen, 1.0)
            
            # High specification multipliers
            high_spec_mult = 1.0
            
            # Impedance control
            impedance_control = getattr(params, 'impedance_control', 'no')
            if impedance_control in self.config.high_spec_multipliers.get('impedance_control', {}):
                high_spec_mult *= self.config.high_spec_multipliers['impedance_control'][impedance_control]
            
            # Gold fingers
            gold_fingers = getattr(params, 'gold_fingers', 'no')
            if gold_fingers in self.config.high_spec_multipliers.get('gold_fingers', {}):
                high_spec_mult *= self.config.high_spec_multipliers['gold_fingers'][gold_fingers]
            
            # Stencil
            stencil = getattr(params, 'stencil', 'no')
            if stencil in self.config.high_spec_multipliers.get('stencil', {}):
                high_spec_mult *= self.config.high_spec_multipliers['stencil'][stencil]
            
            # Mark on PCB
            mark_on_pcb = getattr(params, 'mark_on_pcb', 'no')
            if mark_on_pcb in self.config.high_spec_multipliers.get('mark_on_pcb', {}):
                high_spec_mult *= self.config.high_spec_multipliers['mark_on_pcb'][mark_on_pcb]
            
            # Confirm production file
            confirm_production_file = getattr(params, 'confirm_production_file', 'no')
            if confirm_production_file in self.config.high_spec_multipliers.get('confirm_production_file', {}):
                high_spec_mult *= self.config.high_spec_multipliers['confirm_production_file'][confirm_production_file]
            
            # Electrical test
            electrical_test = getattr(params, 'electrical_test', 'optical manual inspection')
            if electrical_test in self.config.high_spec_multipliers.get('electrical_test', {}):
                high_spec_mult *= self.config.high_spec_multipliers['electrical_test'][electrical_test]
            
            multipliers.high_spec = high_spec_mult
            
            logger.debug(f"Calculated multipliers: material={multipliers.material:.2f}, "
                        f"quantity={multipliers.quantity:.2f}, total={multipliers.total():.2f}")
            
            return multipliers
            
        except Exception as e:
            logger.error(f"Failed to calculate multipliers: {e}")
            # Return default multipliers
            return Multipliers()
    
    def get_material_multiplier(self, material: BaseMaterial) -> float:
        """Get multiplier for specific material."""
        return self.config.material_multipliers.get(material.value, 1.0)
    
    def get_quantity_multiplier(self, quantity: int) -> float:
        """Get multiplier for specific quantity."""
        return self.quantity_func(quantity)
    
    def get_via_hole_multiplier(self, via_hole: MinViaHole) -> float:
        """Get multiplier for specific via hole size."""
        return self.config.via_hole_multipliers.get(float(via_hole.value), 1.0)
    
    def get_tolerance_multiplier(self, tolerance: BoardOutlineTolerance) -> float:
        """Get multiplier for specific tolerance."""
        return self.config.tolerance_multipliers.get(tolerance.value, 1.0)
    
    def update_config(self, new_config: PricingConfig):
        """Update pricing configuration and recompile rules."""
        self.config = new_config
        self._compile_rules()
        logger.info("Pricing configuration updated")
    
    def get_pricing_info(self) -> Dict[str, Any]:
        """Get current pricing configuration for API responses."""
        return {
            "material_multipliers": self.config.material_multipliers,
            "quantity_brackets": self.config.quantity_brackets,
            "thickness_multipliers": self.config.thickness_multipliers,
            "copper_weight_multipliers": self.config.copper_weight_multipliers,
            "via_hole_multipliers": self.config.via_hole_multipliers,
            "tolerance_multipliers": self.config.tolerance_multipliers,
            "color_multipliers": self.config.color_multipliers,
            "surface_finish_multipliers": self.config.surface_finish_multipliers,
            "total_possible_combinations": self._calculate_total_combinations()
        }
    
    def _calculate_total_combinations(self) -> int:
        """Calculate total number of possible pricing combinations."""
        return (len(self.config.material_multipliers) * 
                len(self.config.quantity_brackets) * 
                len(self.config.thickness_multipliers) * 
                len(self.config.copper_weight_multipliers) * 
                len(self.config.via_hole_multipliers) * 
                len(self.config.tolerance_multipliers) * 
                len(self.config.color_multipliers) * 
                len(self.config.surface_finish_multipliers))
    
    def validate_multipliers(self, multipliers: Multipliers) -> List[str]:
        """Validate multipliers and return warnings if any."""
        warnings = []
        
        if multipliers.material <= 0:
            warnings.append("Material multiplier must be positive")
        
        if multipliers.quantity <= 0:
            warnings.append("Quantity multiplier must be positive")
        
        if multipliers.total() > 10.0:
            warnings.append(f"Total multiplier is very high: {multipliers.total():.2f}")
        
        if multipliers.total() < 0.1:
            warnings.append(f"Total multiplier is very low: {multipliers.total():.2f}")
        
        return warnings

# Global rules engine instance
pricing_rules_engine = PricingRulesEngine()
