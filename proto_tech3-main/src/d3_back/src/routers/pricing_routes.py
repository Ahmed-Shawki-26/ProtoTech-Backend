# d3_back/src/routers/pricing_routes.py

from fastapi import APIRouter, HTTPException
from src.d3_back.src.models.schemas import PrintRequest, PriceResponse, AvailableOptionsResponse
from src.d3_back.src.services.pricing_service import PricingService

router = APIRouter()

@router.get("/available-options", response_model=AvailableOptionsResponse)
def get_available_options():
    """Get available 3D printing technologies, materials, and colors from inventory."""
    try:
        return PricingService.get_available_options()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@router.post("/3d_pricing", response_model=PriceResponse)
def calculate_price(request: PrintRequest):
    """Calculate the price for a 3D print based on volume, material, and other options."""
    try:
        return PricingService.calculate_price(request)
    except HTTPException:
        # Re-raise HTTP exceptions from the service layer
        raise
    except RuntimeError as e:
        # Catches the Google Sheets connection error
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")