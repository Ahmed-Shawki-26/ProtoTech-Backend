from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

# Add startup logging
print("🚀 Starting ProtoTech Backend Server...")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"🐍 Python path: {sys.executable}")
print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")

app = FastAPI(
    title="ProtoTech Manufacturing API",
    description="Complete manufacturing platform for PCB production, 3D printing, user management, and e-commerce functionality.",
    version="2.0.0",
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
        "http://localhost:*",
        "http://127.0.0.1:*",
        "https://proto-tech-frontend.vercel.app",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    print("✅ FastAPI application startup completed successfully")
    print("🔗 Health check endpoint available at: /health")
    print("🔗 Root endpoint available at: /")
    print("🔗 Test endpoint available at: /test")

@app.get("/")
async def read_root():
    """A simple health-check endpoint."""
    return {"status": "ok", "message": "ProtoTech API is running"}

@app.get("/health")
async def health_check():
    """Simple health check endpoint for Railway"""
    try:
        # Basic health check - just return OK if the app is running
        return {
            "status": "ok", 
            "message": "ProtoTech API is healthy",
            "environment": os.getenv('ENVIRONMENT', 'development'),
            "version": "2.0.0"
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Health check failed: {str(e)}"
        }

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint that should always work."""
    return {"message": "Backend is working!", "status": "ok"}

# Basic e-commerce endpoints
@app.get("/ecommerce/products")
async def get_products():
    """Get a list of products."""
    return [
        {
            "id": 1,
            "name": "Test Product 1",
            "price": 29.99,
            "description": "This is a test product"
        },
        {
            "id": 2,
            "name": "Test Product 2", 
            "price": 49.99,
            "description": "Another test product"
        }
    ]

@app.get("/ecommerce/categories")
async def get_categories():
    """Get a list of categories."""
    return [
        {
            "id": 1,
            "name": "Test Category",
            "product_count": 2
        }
    ]

@app.get("/api/v1/ecommerce/products")
async def get_products_v1():
    """Get a list of products (v1 API)."""
    return await get_products()

@app.get("/api/v1/ecommerce/categories")
async def get_categories_v1():
    """Get a list of categories (v1 API)."""
    return await get_categories()

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting FastAPI application directly...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
