

# app/schemas/pcb.py

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

# ... (All your existing Enums and the ManufacturingParameters model remain unchanged) ...
class BaseMaterial(str, Enum):
    fr4 = "FR-4"
    flex = "Flex"
    aluminum="Aluminum"
    copper_core="Copper Core"
    rogers="Rogers"
    ptfe_teflon="PTFE Teflon"
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
    """A comprehensive model for all user-selectable PCB manufacturing options."""
    
    # --- Basic Parameters ---
    
    # --- THIS IS THE FIX: Add quantity to this model ---
    quantity: int = Field(..., gt=0, description="The number of PCBs to be manufactured.")
    base_material: BaseMaterial = Field(BaseMaterial.fr4, description="The core material of the PCB.")    
    base_material: BaseMaterial = Field(BaseMaterial.fr4, description="The core material of the PCB.")
    different_designs: int = Field(1, ge=1, description="Number of different PCB designs in a single order.")
    delivery_format: DeliveryFormat = Field(DeliveryFormat.single_pcb, description="How the PCBs are delivered.")
    pcb_thickness_mm: float = Field(1.6, description="Thickness of the final PCB in mm.")
    pcb_color: SolderMaskColor = Field(SolderMaskColor.green, description="Soldermask color.")
    silkscreen: SilkscreenColor = Field(SilkscreenColor.white, description="Color of the text and markings.")
    surface_finish: SurfaceFinish = Field(SurfaceFinish.hasl, description="Type of surface coating on copper pads.")
    
    # --- Advanced Parameters ---
    outer_copper_weight: CopperWeight = Field(CopperWeight.one_oz, description="Copper thickness on outer layers.")
    via_covering: ViaCovering = Field(ViaCovering.tented, description="How vias are treated.")
    min_via_hole_size_dia: str = Field("0.3mm/(0.4/0.45mm)", description="Minimum via hole size and its annular ring diameter.")
    board_outline_tolerance: BoardOutlineTolerance = Field(BoardOutlineTolerance.regular, description="Routing precision for the board outline.")
    confirm_production_file: bool = Field(False, description="If true, user must confirm the production file before manufacturing.")
    mark_on_pcb: MarkOnPCB = Field(MarkOnPCB.order_number, description="How/if a traceability mark will appear on the PCB.")
    electrical_test: bool = Field(True, description="Whether to perform a Flying Probe Fully Test.")
    gold_fingers: bool = Field(False, description="If true, the board has gold-plated edge connectors.")
    edge_plating: bool = Field(False, description="If true, the edges of the board will be plated.")
    blind_slots: bool = Field(False, description="If true, the board contains blind slots.")
    
    # --- Final Touches ---
    four_wire_kelvin_test: bool = Field(False, description="Whether to perform a 4-wire Kelvin test for small resistances.")
    paper_between_pcbs: bool = Field(False, description="If true, paper will be placed between boards to prevent scratches.")
    appearance_quality: AppearanceQuality = Field(AppearanceQuality.ipc_class_2, description="Specifies the visual quality standard.")
    silkscreen_technology: SilkscreenTechnology = Field(SilkscreenTechnology.inkjet_screen_printing, description="The technology used for printing the silkscreen.")
    package_box: PackageBox = Field(PackageBox.with_logo, description="Specifies the type of packaging box.")

class BoardDimensions(BaseModel):
    """Represents the physical dimensions and area of the PCB."""
    width_mm: float
    height_mm: float
    area_m2: float



class PriceQuote(BaseModel):
    """Represents the final calculated price quote."""
    direct_cost_egp: float
    shipping_cost_egp: float
    customs_rate_egp: float
    final_price_egp: float
    currency: str = "EGP"
    details: dict

# --- UPDATED: Main response model now includes the images and layer info ---
class GerberQuoteResponse(BaseModel):
    """The complete response after processing a Gerber file."""
    dimensions: Optional[BoardDimensions]
    quote: Optional[PriceQuote]
    parameters_received: ManufacturingParameters






