from typing import Optional
from app.core.config import settings
from app.schemas.pcb import BoardDimensions, PriceQuote, ManufacturingParameters, BaseMaterial

class PriceCalculator:
    """
    Service for calculating PCB prices based on dimensions and manufacturing parameters.
    This service can be used for price recalculation without requiring file upload.
    """
    
    # Material-specific density (g/cm³) for weight calculations
    MATERIAL_DENSITIES = {
        BaseMaterial.fr4: 1.85,  # Standard FR-4 density
        BaseMaterial.flex: 1.4,  # Flex PCB density
        BaseMaterial.aluminum: 2.7,  # Aluminum density
        BaseMaterial.copper_core: 8.9,  # Copper density
        BaseMaterial.rogers: 1.9,  # Rogers material density
        BaseMaterial.ptfe_teflon: 2.2,  # PTFE density
    }
    
    def _get_material_density(self, material: BaseMaterial) -> float:
        """
        Get the density for a specific material.
        
        Args:
            material: The base material
            
        Returns:
            Density in g/cm³
        """
        return self.MATERIAL_DENSITIES.get(material, settings.FR4_DENSITY_G_PER_CM3)
    
    def calculate_price(self, dimensions: BoardDimensions, params: ManufacturingParameters) -> PriceQuote:
        """
        Calculate the price based on existing dimensions and manufacturing parameters.
        Uses robust error handling to prevent crashes.
        
        Args:
            dimensions: The PCB dimensions (width, height, area)
            params: The manufacturing parameters (quantity, thickness, etc.)
            
        Returns:
            PriceQuote: The calculated price breakdown
        """
        try:
            area_m2 = dimensions.area_m2
            
            # Calculate effective exchange rate
            effective_rate = settings.YUAN_TO_EGP_RATE * settings.EXCHANGE_RATE_BUFFER
            
            # Calculate direct cost
            single_board_cost_yuan = settings.FIXED_ENGINEERING_FEE_YUAN + (area_m2 * settings.PRICE_PER_M2_YUAN)
            direct_cost_yuan = single_board_cost_yuan * params.quantity
            direct_cost_egp = direct_cost_yuan * effective_rate
            
            # Calculate shipping cost based on weight
            width_cm = dimensions.width_mm / 10.0
            height_cm = dimensions.height_mm / 10.0
            thickness_cm = params.pcb_thickness_mm / 10.0
            single_pcb_volume_cm3 = width_cm * height_cm * thickness_cm
            
            # Use material-specific density for weight calculation
            material_density = self._get_material_density(params.base_material)
            single_pcb_weight_g = single_pcb_volume_cm3 * material_density
            total_weight_kg = (single_pcb_weight_g * params.quantity) / 1000.0
            shipping_cost_yuan = total_weight_kg * settings.SHIPPING_COST_PER_KG_YUAN
            shipping_cost_egp = shipping_cost_yuan * effective_rate
            
            # Calculate customs rate
            customs_rate_egp = (direct_cost_egp + shipping_cost_egp) * settings.CUSTOMS_RATE_MULTIPLIER
            
            # Determine final price multiplier based on area
            if area_m2 >= 1.0:
                final_price_multiplier = settings.FINAL_PRICE_MULTIPLIER_LARGE_AREA
            elif area_m2 >= 0.5:
                final_price_multiplier = settings.FINAL_PRICE_MULTIPLIER_MID_AREA
            else:
                final_price_multiplier = settings.FINAL_PRICE_MULTIPLIER_DEFAULT
                
            # Calculate final price
            final_price_egp = customs_rate_egp * final_price_multiplier

            return PriceQuote(
                direct_cost_egp=round(direct_cost_egp, 2),
                shipping_cost_egp=round(shipping_cost_egp, 2),
                customs_rate_egp=round(customs_rate_egp, 2),
                final_price_egp=round(final_price_egp, 2),
                currency="EGP",
                details={
                    "quantity": params.quantity,
                    "area_m2_per_board": area_m2,
                    "pcb_thickness_mm": params.pcb_thickness_mm,
                    "material": str(params.base_material),
                    "material_density_g_per_cm3": material_density,
                    "total_weight_kg": round(total_weight_kg, 3),
                    "yuan_to_egp_rate_used": effective_rate,
                    "final_price_multiplier_used": final_price_multiplier
                }
            )
            
        except Exception as e:
            print(f"❌ Error in price calculation: {e}")
            # Return a basic fallback price to prevent crashes
            return PriceQuote(
                direct_cost_egp=100.0,
                shipping_cost_egp=50.0,
                customs_rate_egp=25.0,
                final_price_egp=500.0,
                currency="EGP",
                details={
                    "error": str(e),
                    "note": "Fallback price due to calculation error",
                    "material": str(params.base_material),
                    "quantity": getattr(params, 'quantity', 1)
                }
            ) 