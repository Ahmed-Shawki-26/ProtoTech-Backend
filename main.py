# main.py

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings
from app.api.main import api_router
# from stripe.main import router as stripe_router  # Temporarily disabled due to configuration issues

# Import auth and user routers
from app.auth.controller import router as auth_router
from app.users.controller import router as users_router
from app.orders.controller import router as orders_router
from app.cart.controller import router as cart_router
from app.database.core import Base, engine
from app.core.infrastructure.rate_limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse

# Import e-commerce router
try:
    from app.api.endpoints import ecommerce
    print("✅ Successfully imported ecommerce router")
except ImportError as e:
    print(f"❌ Failed to import ecommerce router: {e}")
    ecommerce = None

# Import models to ensure they are registered with SQLAlchemy
# Use central models file to avoid circular dependency issues
from app.database.models import Order, OrderItem, UserCart, User

# Load environment variables
import os
import signal
import time
import sys
from dotenv import load_dotenv
load_dotenv()

# Add SIGTERM handler to detect platform shutdowns
def handle_term(signum, frame):
    print(f"⚠️ Received signal {signum} (SIGTERM) from platform at {time.time()}")
    print("Platform is shutting down the container")
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_term)

app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
)

# Add session middleware for OAuth (must be added first)
# Explicit cookie settings to ensure state survives Google redirects
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv('SESSION_SECRET_KEY', 'fallback-secret-key'),
    same_site='lax',           # allow cookie on top-level GET redirects
    https_only=os.getenv('ENVIRONMENT') == 'production',  # HTTPS in production only
    max_age=60 * 60 * 2,       # 2 hours
    session_cookie=os.getenv('SESSION_COOKIE_NAME', 'pt_session')
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://proto-tech-frontend.vercel.app",  # Vercel production frontend
        "https://proto-tech-frontend-9aqs0a11r-ahmedshawki2026-3667s-projects.vercel.app",  # Vercel preview deployment
    ],
    allow_origin_regex=r"^https://([a-z0-9-]+\.)?vercel\.app$",  # Allow all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure database tables exist when the app starts (useful in dev/SQLite)
@app.on_event("startup")
async def create_tables_on_startup():
    try:
        print("🔄 Starting database initialization...")
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
        # Don't fail the entire app if DB init fails - just log and continue
        pass
    
    print("✅ FastAPI application startup completed successfully")

# Apply rate limiting middleware - TEMPORARILY DISABLED FOR DEBUGGING
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
#     status_code=429,
#     content={"detail": "Too many requests. Please try again later."}
# ))
# app.add_middleware(SlowAPIMiddleware)
print("⚠️ Rate limiting middleware temporarily disabled for debugging")

# Include the main API router (PCB + 3D Printing + Layout)
app.include_router(api_router, prefix="/api/v1")

# Include Stripe router - Temporarily disabled
# app.include_router(stripe_router, prefix="/api/v1", tags=["Stripe"])

# Include Authentication and User Management routers
# Routers already define their own prefixes (e.g., '/auth', '/users'),
# so we mount them under '/api/v1' to avoid double-prefixing like '/api/v1/auth/auth'
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(users_router, prefix="/api/v1", tags=["Users"])
app.include_router(cart_router, prefix="/api/v1", tags=["Cart"])
app.include_router(orders_router, prefix="/api/v1", tags=["Orders"])

# Keep auth routes only under '/api/v1' to ensure a single, consistent callback path

# Include E-commerce router at root level with '/ecommerce' prefix
# This matches what the frontend expects: /ecommerce/products, /ecommerce/categories
if ecommerce:
    app.include_router(ecommerce.router, prefix="/ecommerce", tags=["E-commerce"])
    # Also include under /api/v1 for proper authentication
    app.include_router(ecommerce.router, prefix="/api/v1/ecommerce", tags=["E-commerce"])
    print("✅ Successfully registered ecommerce router")
else:
    print("❌ Could not register ecommerce router - import failed")
    # TEMPORARY: Add e-commerce endpoints directly to test
    print("🔄 Adding e-commerce endpoints directly to main.py for testing")

# Health check endpoint for production monitoring
@app.get("/health")
async def health_check():
    """Simple health check endpoint for Railway"""
    return {"status": "ok"}

@app.get("/railway/health")
async def railway_health():
    """Railway-specific health check endpoint"""
    return {"status": "ok", "message": "Railway health check passed"}

@app.get("/ecommerce/test")
async def test_ecommerce():
    """Test endpoint to verify e-commerce is working."""
    return {"message": "E-commerce test endpoint is working!", "status": "ok"}

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint that should always work."""
    from datetime import datetime
    return {
        "message": "Backend is working!", 
        "status": "ok", 
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "port": os.getenv("PORT", "8000")
    }

@app.get("/ecommerce/products")
async def get_products(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get a paginated list of all available products."""
    # Return mock data for testing
    mock_products = [
        {
            "id": 1,
            "name": "Test Product 1",
            "qty_available": 10.0,
            "list_price": 29.99,
            "default_code": "TEST001",
            "description_sale": "This is a test product",
            "barcode": "123456789",
            "type": "consu",
            "image_url": None,
            "categ_id": {"id": 1, "name": "Test Category"}
        },
        {
            "id": 2,
            "name": "Test Product 2",
            "qty_available": 5.0,
            "list_price": 49.99,
            "default_code": "TEST002",
            "description_sale": "Another test product",
            "barcode": "987654321",
            "type": "consu",
            "image_url": None,
            "categ_id": {"id": 1, "name": "Test Category"}
        }
    ]
    return mock_products[:limit]

@app.get("/ecommerce/categories")
async def get_categories():
    """Get a list of all product categories."""
    # Return mock data for testing
    return [
        {
            "id": 1,
            "name": "Test Category",
            "parent_id": None,
            "product_count": 2
        }
    ]

@app.get("/", tags=["Root"])
async def read_root():
    """A simple health-check endpoint."""
    return {"status": "ok", "message": "ProtoTech API is running"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FastAPI application directly...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
