

# app/schemas/pcb.py

from pydantic import BaseModel, Field , ConfigDict 
from enum import Enum
from typing import Optional


class PCBThickness(float, Enum):
    t_0_4_mm = 0.4
    t_0_6_mm = 0.6
    t_0_8_mm = 0.8
    t_1_0_mm = 1.0
    t_1_2_mm = 1.2
    t_1_6_mm = 1.6
    t_2_0_mm = 2.0

class MinViaHole(float, Enum):
    h_30_mm = 0.3
    h_25_mm = 0.25
    h_20_mm = 0.20
    h_15_mm = 0.15


# ... (All your existing Enums and the ManufacturingParameters model remain unchanged) ...
class BaseMaterial(str, Enum):
    fr4 = "FR-4"
    flex = "Flex"
class DeliveryFormat(str, Enum):
    single_pcb = "Single PCB"
    panel_by_customer = "Panel by Customer"
    panel_by_ProtoTech = "Panel by Proto-Tech"

class SolderMaskColor(str, Enum):
    green = "Green"
    purple = "Purple"
    red = "Red"
    yellow = "Yellow"
    blue = "Blue"
    white = "White"
    black = "Black"

class SilkscreenColor(str, Enum):
    white = "White"
    black = "Black" # Typically for white solder mask

class SurfaceFinish(str, Enum):
    hasl = "HASL (with lead)"
    hasl_lead_free = "LeadFree HASL (RoHS)"
    enig = "ENIG"

class CopperWeight(str, Enum):
    one_oz = "1 oz"
    two_oz = "2 oz"

class ViaCovering(str, Enum):
    tented = "Tented"
    untented = "Untented"
    plugged = "Plugged"
    epoxy_filled = "Epoxy Filled & Capped"
    copper_paste_filled = "Copper Paste Filled & Capped"

class BoardOutlineTolerance(str, Enum):
    regular = "±0.2mm (Regular)"
    precision = "±0.1mm (Precision)"

class MarkOnPCB(str, Enum):
    order_number = "Order Number"
    specify_position = "Order Number (Specify Position)"
    barcode = "2D Barcode (Serial Number)"
    remove_mark = "Remove Mark"

class AppearanceQuality(str, Enum):
    ipc_class_2 = "IPC Class 2 Standard"
    superb = "Superb Quality"

class SilkscreenTechnology(str, Enum):
    inkjet_screen_printing = "Ink-jet/Screen Printing"
    high_precision_printing = "High-precision Printing"

class PackageBox(str, Enum):
    with_logo = "With Proto-Tech logo"
    blank_box = "Blank box"

# ===================================================================
#  Main Pydantic Model for Manufacturing Parameters
# ===================================================================
class ManufacturingParameters(BaseModel):
    """A simplified model containing only the parameters that affect the price quote."""
    model_config = ConfigDict(extra="allow") 

    quantity: int = Field(..., gt=0, description="The number of PCBs to be manufactured.")
    
    different_designs: int = Field(
        1, ge=1,le=50, description="Number of different PCB designs in a single order."
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
    
# --- UPDATED: Main response model now includes the images ---
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



