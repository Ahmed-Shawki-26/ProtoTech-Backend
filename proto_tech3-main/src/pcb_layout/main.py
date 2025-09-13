from fastapi import APIRouter
from src.pcb_layout.api.endpoints.layout import router as layout_router # <-- IMPORT the new router
router=APIRouter()
router.include_router(layout_router)


