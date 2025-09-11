# app/api/main.py

from fastapi import APIRouter
from .endpoints import pcb, printing_3d, ecommerce, layout

# Create main API router
api_router = APIRouter()

# Include PCB endpoints with prefix
api_router.include_router(
    pcb.router,
    prefix="/pcb",
    tags=["PCB Manufacturing"]
)

# Include 3D printing endpoints with prefix
api_router.include_router(
    printing_3d.router,
    prefix="/3d-printing",
    tags=["3D Printing"]
)

# Include PCB Layout endpoints with prefix
api_router.include_router(
    layout.router,
    prefix="/layout",
    tags=["PCB Layout Service"]
)

# Include E-commerce endpoints with prefix
api_router.include_router(
    ecommerce.router,
    prefix="/ecommerce",
    tags=["E-commerce"]
) 