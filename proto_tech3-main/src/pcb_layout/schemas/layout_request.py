# app/schemas/layout_request.py

from pydantic import BaseModel, Field
from enum import Enum
from typing import List

# --- Enums for the new service options ---

class LayoutServiceType(str, Enum):
    design = "PCB Layout Design"
    modify = "PCB Layout Modify"

class PcbType(str, Enum):
    rigid = "Regular Rigid PCB"
    flex = "Flex PCB"

class ComponentSides(str, Enum):
    top = "Top only"
    bottom = "Bottom only"
    both = "Both sides"

# --- Main Pydantic Model for the Layout Request ---

class LayoutRequestParameters(BaseModel):
    """A model for all user-selectable parameters for a PCB layout service request."""
    
    service_type: LayoutServiceType = Field(..., description="The type of layout service requested.")
    pcb_type: PcbType = Field(..., description="The general type of the PCB.")
    layers: int = Field(..., ge=1, le=6, description="The number of copper layers required.")
    width_mm: float = Field(..., gt=0, description="The target width of the PCB in millimeters.")
    height_mm: float = Field(..., gt=0, description="The target height of the PCB in millimeters.")
    pad_count: int = Field(..., ge=5, le=1000, description="The estimated number of pads/pins on the board.")
    
    # These are boolean because they correspond to the "Yes/No" buttons
    order_pcba_at_proto_tech: bool = Field(..., description="Will the user also order PCBA for this design?")
    
    # This will be a list of strings from the checkboxes
    delivery_formats: List[str] = Field(..., description="A list of the final file formats the user wants to receive.")
    
    # Optional text field
    remark: str = Field("", description="Optional user remarks or special instructions.")

class LayoutQuoteResponse(BaseModel):
    """The confirmation response sent back to the user."""
    request_id: str = Field(..., description="A unique ID for the submitted layout request.")
    message: str = "Your layout request has been successfully submitted. Our team will review the files and contact you with a quote shortly."
    details_received: LayoutRequestParameters