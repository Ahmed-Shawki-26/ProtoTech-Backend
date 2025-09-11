# app/api/endpoints/layout.py

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import ValidationError
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
import uuid
import os
import tempfile
from datetime import datetime

router = APIRouter()

# --- Schemas ---
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

# --- Service Class ---
class LayoutService:
    """Handles the business logic for a new PCB layout quote request."""

    def __init__(self, params: LayoutRequestParameters, requirements_file: UploadFile, 
                 schematic_file: UploadFile, other_files: List[UploadFile]):
        self.params = params
        self.requirements_file = requirements_file
        self.schematic_file = schematic_file
        self.other_files = other_files or []

    def process_request(self) -> str:
        """Process the layout request and return a unique request ID."""
        request_id = str(uuid.uuid4())[:8].upper()
        
        # Create a directory for this request
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        request_dir = f"layout_requests/{timestamp}_{request_id}"
        os.makedirs(request_dir, exist_ok=True)
        
        # Save all files
        self._save_file(self.requirements_file, "requirements", request_dir)
        self._save_file(self.schematic_file, "schematic", request_dir)
        
        for i, other_file in enumerate(self.other_files):
            self._save_file(other_file, f"other_{i+1}", request_dir)
        
        # Save parameters as JSON
        params_file = os.path.join(request_dir, "parameters.json")
        with open(params_file, 'w') as f:
            f.write(self.params.model_dump_json(indent=2))
        
        return request_id

    def _save_file(self, file: Optional[UploadFile], prefix: str, base_path: Optional[str] = None):
        """Save an uploaded file with a descriptive name."""
        if not file or not file.filename:
            return None
            
        # Create safe filename
        safe_filename = f"{prefix}_{file.filename}"
        file_path = os.path.join(base_path or ".", safe_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)
        
        return file_path

# --- Endpoints ---
@router.post(
    "/request-layout-quote/",
    response_model=LayoutQuoteResponse,
    summary="Submit a PCB Layout Design/Modification Request",
    description="Upload schematic, requirements, and other files along with design parameters to receive a manual quote."
)
async def request_layout_quote(
    params_json: str = Form(..., description="A JSON string of the LayoutRequestParameters."),
    requirements_file: UploadFile = File(..., description="Layout requirements (.txt, .pdf, .doc, .docx)."),
    schematic_file: UploadFile = File(..., description="Schematic & PCB file (.epro, .zip, .rar)."),
    other_files: Optional[List[UploadFile]] = File(None, description="Other supporting files (.dxf, .bin, .hex, etc.).")
):
    """
    This endpoint handles a complete PCB layout service request. It accepts multiple
    files and a JSON string of parameters, saves them, and returns a confirmation.
    """
    try:
        params = LayoutRequestParameters.model_validate_json(params_json)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Ensure other_files is a list even if it's None
    other_files_list = other_files or []

    try:
        service = LayoutService(
            params=params,
            requirements_file=requirements_file,
            schematic_file=schematic_file,
            other_files=other_files_list
        )
        request_id = service.process_request()
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while processing your request.")

    return LayoutQuoteResponse(
        request_id=request_id,
        details_received=params
    )
