# app/api/endpoints/pcb.py

import os
import io
import zipfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import ValidationError

from src.app.services.quote_generator import QuoteGenerator
# We import the corrected schema that no longer has an 'images' field.
from src.app.schemas.pcb import ManufacturingParameters, GerberQuoteResponse

router = APIRouter()

@router.post(
    "/generate-quote/",
    summary="Generate Full PCB Quote from Gerber ZIP",
    description="Upload a ZIP file and provide manufacturing options as a JSON string. Returns a new ZIP containing rendered images and a detailed quote.json file."
)
async def generate_full_quote(
    file: UploadFile = File(..., description="A ZIP file containing Gerber layers."),
    params_json: str = Form(
        ...,
        description="A JSON string representing the ManufacturingParameters.",
        example='{"quantity": 10, "base_material": "FR-4", ...}'
    )
):
    """
    This endpoint accepts a file upload and a form field containing a JSON string
    of manufacturing parameters. It returns a single ZIP archive containing:
    - `pcb_top.png`: The rendered top view of the board.
    - `pcb_bottom.png`: The rendered bottom view of the board.
    - `quote_details.json`: A file with the full quote, dimensions, and parameters received.
    """
    # 1. Validate the uploaded file type
    if not file.filename or not (file.filename.lower().endswith('.zip') or file.filename.lower().endswith('.rar')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP or RAR file.")

    # 2. Validate and parse the incoming JSON string into a Pydantic model
    try:
        params = ManufacturingParameters.model_validate_json(params_json)
    except ValidationError as e:
        # If validation fails, return a detailed 422 error
        raise HTTPException(status_code=422, detail=e.errors())

    archive_content = await file.read()

    # 3. Delegate all the core logic to the service layer
    try:
        generator = QuoteGenerator(
            archive_content=archive_content,
            filename=file.filename,
            params=params
        )
        top_image_bytes, bottom_image_bytes, dimensions, quote = generator.process()
        
    except ValueError as e: # Catches specific, expected errors from our service
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e: # Catches any other unexpected server errors
        # In a real production app, you would log this error.
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred during processing.")

    # 4. Construct the JSON data object using our clean Pydantic schema
    # This object will become the content of our .json file.
    response_data = GerberQuoteResponse(
        dimensions=dimensions,
        quote=quote,
        parameters_received=params,
    )

    # 5. Create the response ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
        # Add the rendered images
        zip_out.writestr("pcb_top.png", top_image_bytes)
        zip_out.writestr("pcb_bottom.png", bottom_image_bytes)
        
        # Add the structured JSON data file
        # .model_dump_json() is the correct method for Pydantic v2+
        zip_out.writestr(
            "quote_details.json",
            response_data.model_dump_json(indent=2)
        )

    # Prepare the buffer for reading
    zip_buffer.seek(0)
    
    # Create a safe, descriptive filename for the download
    original_filename = os.path.splitext(file.filename)[0]
    response_filename = f"quote_for_{original_filename}.zip"

    # 6. Stream the ZIP file back to the client
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={response_filename}"}
    )

@router.post(
    "/generate-quote-fast/",
    summary="Generate PCB Quote without Rendering Images",
    description="Upload a ZIP file and provide manufacturing options as a JSON string. Returns a JSON object with the quote details."
)
async def generate_quote_fast(
    file: UploadFile = File(..., description="A ZIP file containing Gerber layers."),
    params_json: str = Form(
        ...,
        description="A JSON string representing the ManufacturingParameters.",
        example='{"quantity": 10, "base_material": "FR-4", ...}'
    )
):
    """
    This endpoint accepts a file upload and a form field containing a JSON string
    of manufacturing parameters. It returns a JSON response containing:
    - `quote_details.json`: A file with the full quote, dimensions, and parameters received.
    """
    # 1. Validate the uploaded file type
    if not file.filename or not (file.filename.lower().endswith('.zip') or file.filename.lower().endswith('.rar')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP or RAR file.")

    # 2. Validate and parse the incoming JSON string into a Pydantic model
    try:
        params = ManufacturingParameters.model_validate_json(params_json)
    except ValidationError as e:
        # If validation fails, return a detailed 422 error
        raise HTTPException(status_code=422, detail=e.errors())

    archive_content = await file.read()

    # 3. Delegate all the core logic to the service layer
    try:
        generator = QuoteGenerator(
            archive_content=archive_content,
            filename=file.filename,
            params=params
        )
        dimensions, quote = generator.process_quote_only()
        
    except ValueError as e: # Catches specific, expected errors from our service
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e: # Catches any other unexpected server errors
        # In a real production app, you would log this error.
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred during processing.")

    # 4. Construct the JSON data object using our clean Pydantic schema
    # This object will become the content of our .json file.
    response_data = GerberQuoteResponse(
        dimensions=dimensions,
        quote=quote,
        parameters_received=params,
    )

    # 5. Return the JSON response
    return JSONResponse(content=response_data.model_dump())