# app/services/layout_service.py

import os
import uuid
from datetime import datetime
from fastapi import UploadFile
from typing import List, Optional

from src.pcb_layout.schemas.layout_request import LayoutRequestParameters

class LayoutService:
    """Handles the business logic for a new PCB layout quote request."""

    def __init__(self, params: LayoutRequestParameters, requirements_file: UploadFile, schematic_file: UploadFile, other_files: List[UploadFile]):
        self._params = params
        self._requirements_file = requirements_file
        self._schematic_file = schematic_file
        self._other_files = other_files
        self._request_id = f"layout-req-{uuid.uuid4().hex[:8]}"
        self._storage_path = os.path.join("layout_requests", datetime.now().strftime('%Y-%m-%d'), self._request_id)

    def process_request(self) -> str:
        """
        Processes the layout request by saving all files and parameters.
        Returns the unique request ID.
        """
        print(f"Processing new layout request: {self._request_id}")
        
        # 1. Create a dedicated directory for this request
        os.makedirs(self._storage_path, exist_ok=True)

        # 2. Save the uploaded files
        self._save_file(self._requirements_file, "requirements")
        self._save_file(self._schematic_file, "schematic")
        
        other_files_path = os.path.join(self._storage_path, "other_files")
        os.makedirs(other_files_path, exist_ok=True)
        for i, file in enumerate(self._other_files):
            self._save_file(file, f"other_{i+1}", base_path=other_files_path)

        # 3. Save the parameters as a JSON file
        params_path = os.path.join(self._storage_path, "request_parameters.json")
        with open(params_path, "w") as f:
            # Use .model_dump_json() for Pydantic v2+
            f.write(self._params.model_dump_json(indent=2))

        print(f"Successfully saved all files for request {self._request_id} to {self._storage_path}")
        
        # In a real application, you would now trigger an email notification
        # to your engineering team with the request_id and path.
        # self._send_email_notification()

        return self._request_id

    def _save_file(self, file: Optional[UploadFile], prefix: str, base_path: Optional[str] = None):
        """Helper function to save an uploaded file to the request directory."""
        if not file or not file.filename:
            return

        # Use the provided base_path or the main storage path
        path_to_save = base_path or self._storage_path
        
        # Create a safe filename
        safe_filename = f"{prefix}_{file.filename.replace(' ', '_')}"
        file_location = os.path.join(path_to_save, safe_filename)
        
        with open(file_location, "wb+") as file_object:
            file_object.write(file.file.read())
        print(f"  - Saved file: {file_location}")