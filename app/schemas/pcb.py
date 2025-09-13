

# app/schemas/pcb.py

from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from typing import Optional

class PCBThickness(str, Enum):
    t_0_4_mm = "0.4mm"
    t_0_6_mm = "0.6mm"
    t_0_8_mm = "0.8mm"
    t_1_0_mm = "1.0mm"
    t_1_2_mm = "1.2mm"
    t_1_6_mm = "1.6mm"
    t_2_0_mm = "2.0mm"
    t_0_12_mm = "0.12mm"  # Flex default

class MinViaHole(str, Enum):
    h_30_mm = "0.3mm"
    h_25_mm = "0.25mm"
    h_20_mm = "0.20mm"
    h_15_mm = "0.15mm"

class BaseMaterial(str, Enum):
    fr4 = "FR-4"
    flex = "Flex"
    aluminum = "Aluminum"
    copper_core = "Copper Core"
    rogers = "Rogers"
    ptfe_teflon = "PTFE"
class DeliveryFormat(str, Enum):
    single_pcb = "Single PCB"
    panel_by_customer = "Panel by Customer"
    panel_by_ProtoTech = "Panel by Proto-Tech"

class SolderMaskColor(str, Enum):
    green = "Green"
    red = "Red"
    yellow = "Yellow"
    blue = "Blue"
    white = "White"
    black = "Black"

class SilkscreenColor(str, Enum):
    white = "White"
    black = "Black" # Typically for white solder mask

class SurfaceFinish(str, Enum):
    immersed_tin = "Immersed Tin"

class CopperWeight(str, Enum):
    one_third_oz = "1/3 oz"  # Flex default
    one_oz = "1 oz"          # Default
    two_oz = "2 oz"          # High copper weight

class ViaCovering(str, Enum):
    tented = "Tented"
    untented = "Untented"
    plugged = "Plugged"

class BoardOutlineTolerance(str, Enum):
    regular = "±0.2mm (Regular)"
    precision = "±0.1mm (Precision)"

# ===================================================================
#  Main Pydantic Model for Manufacturing Parameters
# ===================================================================
class ManufacturingParameters(BaseModel):
    """A simplified model containing only the parameters that affect the price quote."""
    model_config = ConfigDict(extra="allow") 

    quantity: int = Field(..., gt=0, description="The number of PCBs to be manufactured.")
    
    different_designs: int = Field(
        1, ge=1, le=50, description="Number of different PCB designs in a single order."
    )
    
    delivery_format: DeliveryFormat = Field(
        DeliveryFormat.single_pcb, 
        description="How the PCBs are delivered. 'Panel by Customer' may affect pricing based on the number of designs."
    )
    
    pcb_thickness_mm: PCBThickness = Field(
        PCBThickness.t_1_6_mm, # Default to 1.6mm
        description="Thickness of the final PCB in mm. Must be one of the allowed values."
    )
    
    
    pcb_color: SolderMaskColor = Field(
        SolderMaskColor.green, 
        description="Soldermask color. Non-green colors incur a surcharge and extra manufacturing time."
    )
    
    surface_finish: SurfaceFinish = Field(
        SurfaceFinish.immersed_tin,
        description="Type of surface coating on copper pads. Only Immersed Tin is available for local manufacturing."
    )
    
    confirm_production_file: str = Field(
        "No",
        description="Whether to confirm the production file before manufacturing."
    )
    
    electrical_test: str = Field(
        "optical manual inspection",
        description="Type of electrical testing to perform."
    )
    
    via_covering: ViaCovering = Field(
        ViaCovering.tented,
        description="Via covering type."
    )
    
    outer_copper_weight: CopperWeight = Field(
        CopperWeight.one_oz, 
        description="Copper thickness on outer layers. '2 oz' is more expensive."
    )
    
    min_via_hole_size_dia: MinViaHole = Field(
        MinViaHole.h_30_mm, 
        description="Minimum via hole size. Holes smaller than 0.3mm may incur a surcharge."
    )
    
    board_outline_tolerance: BoardOutlineTolerance = Field(
        BoardOutlineTolerance.regular, 
        description="Routing precision for the board outline. '±0.1mm (Precision)' is more expensive."
    )
    
    silkscreen: SilkscreenColor = Field(
        SilkscreenColor.white,
        description="Silkscreen color for component markings. White PCBs use black silkscreen, black PCBs use white silkscreen."
    )

    # Note: `base_material` is kept because it's essential for selecting the correct
    # rendering theme, even if only FR-4 has a defined price model currently.
    base_material: BaseMaterial = Field(
        BaseMaterial.fr4, 
        description="The core material of the PCB. Used for rendering."
    )

class BoardDimensions(BaseModel):
    """Represents the physical dimensions and area of the PCB."""
    width_mm: float
    height_mm: float
    area_m2: float



class PriceQuote(BaseModel):
    """Represents the final calculated price quote."""
    final_price_egp: float
    extra_working_days: int = Field(0, description="Extra manufacturing days due to options like color.")
    currency: str = "EGP"
    # The details dict can hold the breakdown of the calculation for transparency
    details: dict

# --- UPDATED: Main response model now includes the images and layer info ---
class GerberQuoteResponse(BaseModel):
    """The complete response after processing a Gerber file."""
    dimensions: Optional[BoardDimensions]
    quote: Optional[PriceQuote]
    parameters_received: ManufacturingParameters


class PcbCheckoutRequest(BaseModel):
    """
    The request body for initiating a PCB order checkout.
    It contains the manufacturing parameters chosen by the user.
    The Gerber file itself will be sent as a separate part of the request.
    """
    params: ManufacturingParameters


# ===================================================================
#  NEW: Client-Side Recoloring Models
# ===================================================================

class JobResponse(BaseModel):
    """Response when starting an async quote generation job"""
    job_id: str
    status: str

class ImageUrls(BaseModel):
    """URLs for different image sizes"""
    class Config:
        extra = "forbid"
    
    size_256: str = Field(alias="256")
    size_1024: str = Field(alias="1024")

class SideManifest(BaseModel):
    """Manifest for one side (top or bottom) of the PCB"""
    base: ImageUrls
    mask: ImageUrls

class QuoteManifest(BaseModel):
    """Complete manifest with all image URLs for client-side recoloring"""
    renderVersion: str
    sides: dict[str, SideManifest]  # "top" and/or "bottom"

class JobStatus(BaseModel):
    """Status of an async rendering job"""
    status: str  # "queued" | "parsing" | "rendering" | "uploading" | "completed" | "failed"
    progress: Optional[int] = None
    error: Optional[str] = None
    manifest: Optional[QuoteManifest] = None






