# /src/main.py

from fastapi import APIRouter

from src.auth.src.api import register_routes
import os

# --- NEW: Import Request and JSONResponse ---

# --- END NEW ---


app = APIRouter()


register_routes(app)