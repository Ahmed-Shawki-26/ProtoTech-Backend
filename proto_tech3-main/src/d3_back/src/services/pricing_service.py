# d3_back/src/services/pricing_service.py

from fastapi import HTTPException
from src.d3_back.src.models.schemas import PrintRequest, PriceResponse, AvailableOptionsResponse
from src.d3_back.src.config import settings
from src.d3_back.src.utils.inventory import get_inventory_data

class PricingService:

    @staticmethod
    def get_available_options() -> AvailableOptionsResponse:
        """Get available 3D printing technologies, materials, and colors from inventory."""
        inventory_df = get_inventory_data()
        materials_colors = {}
        
        for material in inventory_df['Material_Short'].unique():
            if material in settings.MATERIAL_DENSITIES:
                material_rows = inventory_df[
                    (inventory_df['Material_Short'] == material) &
                    (inventory_df['Remaining (g)'] > 0)
                ]
                colors = material_rows['Color'].unique().tolist()
                if colors:
                    materials_colors[material] = [color.title() for color in colors]
        
        return AvailableOptionsResponse(
            technologies=["FDM"],
            materials=materials_colors
        )

    @staticmethod
    def calculate_price(request: PrintRequest) -> PriceResponse:
        """Calculates the price for a 3D print request after validating against inventory."""
        material_upper = request.material.upper()
        
        if material_upper not in settings.MATERIAL_DENSITIES:
            raise HTTPException(status_code=400, detail=f"Invalid material. Available: {list(settings.MATERIAL_DENSITIES.keys())}")

        # --- Weight Calculation ---
        density = settings.MATERIAL_DENSITIES[material_upper]
        weight_per_unit = request.volume_cm3 * density 
        total_weight_required = weight_per_unit * request.quantity

        # --- Inventory Check ---
        PricingService._check_inventory(material_upper, request.color, total_weight_required)

        # --- Price Calculation ---
        price_per_unit = weight_per_unit * settings.PRICE_PER_GRAM_EGP[material_upper]
        total_price = price_per_unit * request.quantity
        
        return PriceResponse(
            total_price_egp=round(total_price, 2),
            weight_grams=round(total_weight_required, 2),
            price_per_unit_egp=round(price_per_unit, 2),
            quantity=request.quantity,
        )

    @staticmethod
    def _check_inventory(material: str, color: str, weight_required: float):
        """Private helper to check if enough material is in stock."""
        inventory_df = get_inventory_data()
        color_upper = color.upper()

        material_inventory = inventory_df[
            (inventory_df['Material_Short'] == material) &
            (inventory_df['Color_Upper'] == color_upper)
        ]
        
        if material_inventory.empty:
            raise HTTPException(status_code=404, detail=f"Material not found: {material} in color {color}.")

        available_grams = material_inventory['Remaining (g)'].sum()
        if available_grams < weight_required:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough material in stock. Required: {weight_required:.2f}g, Available: {available_grams:.2f}g"
            )