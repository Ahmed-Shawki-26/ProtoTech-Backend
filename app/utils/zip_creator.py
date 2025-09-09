# app/utils/zip_creator.py

import io
import json
import zipfile
from typing import Optional
from app.schemas.pcb import BoardDimensions

def create_response_zip(
    top_image_bytes: bytes,
    bottom_image_bytes: bytes,
    dimensions: Optional[BoardDimensions]
) -> io.BytesIO:
    """Creates an in-memory ZIP file containing rendered images and dimension data."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
        zip_out.writestr("pcb_top.png", top_image_bytes)
        zip_out.writestr("pcb_bottom.png", bottom_image_bytes)
        if dimensions:
            # Use .model_dump_json() for Pydantic v2+
            dimensions_json = dimensions.model_dump_json(indent=2)
            zip_out.writestr("dimensions.json", dimensions_json)
    
    zip_buffer.seek(0)
    return zip_buffer