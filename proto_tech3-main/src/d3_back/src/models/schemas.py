# d3_back/src/models/schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict

class PrintRequest(BaseModel):
    volume_cm3: float = Field(..., gt=0, description="Volume of the object in cubic centimeters")
    material: str = Field(..., example="PLA", description="The printing material (e.g., PLA, ABS).")
    color: str = Field(..., example="Black", description="The desired color of the material.")
    # infill_percentage: float = Field(..., ge=0.1, le=1.0, description="Infill percentage (0.1 to 1.0).")
    quantity: int = Field(..., gt=0, description="Number of items to print.")

class PriceResponse(BaseModel):
    total_price_egp: float
    weight_grams: float
    price_per_unit_egp: float
    quantity: int

class AvailableOptionsResponse(BaseModel):
    technologies: List[str]
    materials: Dict[str, List[str]] # e.g., {"PLA": ["Black", "White"], "ABS": ["Red"]}