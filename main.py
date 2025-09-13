# main.py

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings
from app.api.main import api_router
from app.core.error_handlers import setup_error_handlers, add_request_id_middleware
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
from contextlib import asynccontextmanager

# Phase 3 imports
from app.core.middleware.tenant_middleware import TenantMiddleware
from app.core.monitoring.alerting import alert_manager
from app.core.feature_flags import feature_flags
from app.api.endpoints.monitoring import router as monitoring_router

# Phase 4 imports
from app.services.unified_pricing_engine import unified_pricing_engine
from app.services.advanced_cache_service import advanced_cache
from app.api.endpoints.ab_testing import router as ab_testing_router

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    try:
        print("🔄 Starting database initialization...")
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
        # Don't fail the entire app if DB init fails - just log and continue
        pass
    
    # Clean up expired image cache on startup
    try:
        from app.services.image_cache_service import image_cache
        cleaned_count = image_cache.cleanup_expired_cache()
        if cleaned_count > 0:
            print(f"🧹 Cleaned up {cleaned_count} expired image cache entries on startup")
        else:
            print("✅ Image cache is clean - no expired entries found")
    except Exception as e:
        print(f"⚠️ Image cache cleanup warning: {e}")
        # Don't fail the entire app if cache cleanup fails - just log and continue
        pass
    
    # Start alert manager
    try:
        await alert_manager.start()
        print("✅ Alert manager started successfully")
    except Exception as e:
        print(f"⚠️ Alert manager startup warning: {e}")
    
    # Initialize advanced cache
    try:
        await advanced_cache.initialize()
        print("✅ Advanced cache initialized successfully")
    except Exception as e:
        print(f"⚠️ Advanced cache initialization warning: {e}")
    
    # Warm up unified pricing engine
    try:
        # Pre-calculate common configurations
        cache_stats = unified_pricing_engine.get_cache_stats()
        print(f"✅ Unified pricing engine ready (cache: {cache_stats['size']} entries)")
    except Exception as e:
        print(f"⚠️ Unified pricing engine warmup warning: {e}")
    
    print("✅ FastAPI application startup completed successfully")
    
    yield
    
    # Shutdown
    try:
        await alert_manager.stop()
        print("✅ Alert manager stopped successfully")
    except Exception as e:
        print(f"⚠️ Alert manager shutdown warning: {e}")
    
    try:
        await advanced_cache.cleanup()
        print("✅ Advanced cache cleaned up successfully")
    except Exception as e:
        print(f"⚠️ Advanced cache cleanup warning: {e}")

app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan
)

# Set up error handlers
setup_error_handlers(app)

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

# Add request ID middleware for better error tracking
app.middleware("http")(add_request_id_middleware)

# Add debug middleware for local-price endpoint
@app.middleware("http")
async def debug_middleware(request, call_next):
    """Debug middleware to log local-price requests and catch comparison errors"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Log all requests to local-price endpoint
    if request.url.path == "/api/v1/pcb/local-price/":
        try:
            body = await request.body()
            logger.warning(f"DEBUG: local-price request body: {body}")
            
            # Recreate request for downstream
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
        except Exception as e:
            logger.error(f"DEBUG: Error reading request body: {e}")
    
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"DEBUG: Request failed with: {type(e).__name__}: {str(e)}")
        if "not supported between" in str(e):
            logger.error(f"DEBUG: Comparison error detected: {str(e)}")
            import traceback
            logger.error(f"DEBUG: Full traceback:\n{traceback.format_exc()}")
        raise

# Add tenant isolation middleware
app.add_middleware(TenantMiddleware, default_tenant="default")

# Database initialization and startup logic moved to lifespan context manager

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

# Include monitoring router
app.include_router(monitoring_router, prefix="/api/v1/monitoring", tags=["Monitoring"])

# Include A/B testing router
app.include_router(ab_testing_router, prefix="/api/v1/ab-testing", tags=["A/B Testing"])

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

# Shutdown logic moved to lifespan context manager

@app.get("/", tags=["Root"])
async def read_root():
    """A simple health-check endpoint."""
    return {"status": "ok", "message": "ProtoTech API is running"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FastAPI application directly...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
