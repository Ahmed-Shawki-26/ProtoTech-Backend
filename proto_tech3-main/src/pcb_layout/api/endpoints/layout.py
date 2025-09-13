# app/api/endpoints/layout.py

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import ValidationError
from typing import List, Optional

from src.pcb_layout.schemas.layout_request import LayoutRequestParameters, LayoutQuoteResponse
from src.pcb_layout.services.layout_service import LayoutService

router = APIRouter()

@router.post(
    "/request-layout-quote/",
    response_model=LayoutQuoteResponse,
    summary="Submit a PCB Layout Design/Modification Request",
    description="Upload schematic, requirements, and other files along with design parameters to receive a manual quote."
)
async def request_layout_quote(
    # We use Form for parameters and File for uploads
    params_json: str = Form(..., description="A JSON string of the LayoutRequestParameters."),
    requirements_file: UploadFile = File(..., description="Layout requirements (.txt, .pdf, .doc, .docx)."),
    schematic_file: UploadFile = File(..., description="Schematic & PCB file (.epro, .zip, .rar)."),
    # Use Optional[List[UploadFile]] to allow zero or more "other" files
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
        # In a real app, log the full error
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while processing your request.")

    return LayoutQuoteResponse(
        request_id=request_id,
        details_received=params
    )