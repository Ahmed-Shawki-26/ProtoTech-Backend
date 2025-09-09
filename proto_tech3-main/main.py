# main.py

from fastapi import FastAPI
from src.app.core.config import settings
from src.app.api.endpoints.pcb import router as pcb_router
from src.stripe_.main import router as stripe_router
# from d3_back.src.main import router as d3_router
from src.pcb_layout.main import router as layout_router 
from src.auth.src.main import app as auth_router

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from slowapi.errors import RateLimitExceeded
import os 
from src.auth.src.rate_limiter import limiter

SESSION_SECRET = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET:
    raise ValueError("SESSION_SECRET_KEY environment variable not set!")
os.makedirs("log",exist_ok=True)

app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
)

# Include the router from the pcb endpoint module
app.include_router(pcb_router, prefix="/api/v1", tags=["PCB Processing"])
app.include_router(stripe_router, prefix="/api/v1", tags=["Stripe"])
# app.include_router(d3_router, prefix="/api/v1", tags=["3D Printing"])
app.include_router(layout_router, prefix="/api/v1", tags=["PCB Layout"])
app.include_router(auth_router, prefix="/api/v1")



# --- NEW: Define the exception handler function ---
def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"}
    )
# --- END NEW ---

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Add the rate limiter to the app instance
app.state.limiter = limiter
# Now this line will work because the function is defined above
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/", tags=["Root"])
async def read_root():
    """A simple health-check endpoint."""
    return {"status": "ok", "message": "Welcome to the PCB Renderer API!"}
