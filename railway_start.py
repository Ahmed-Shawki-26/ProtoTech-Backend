#!/usr/bin/env python3
"""
Ultra simple FastAPI app for Railway deployment
This is the absolute minimum needed to get Railway working
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Create FastAPI app
app = FastAPI(title="ProtoTech API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "https://proto-tech-frontend.vercel.app",
        "https://proto-tech-frontend-9aqs0a11r-ahmedshawki2026-3667s-projects.vercel.app",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "ProtoTech API is running", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Health check passed"}

# Add basic e-commerce endpoints for testing
@app.get("/api/v1/ecommerce/products")
async def get_products():
    return [
        {"id": 1, "name": "Test Product 1", "price": 29.99},
        {"id": 2, "name": "Test Product 2", "price": 49.99}
    ]

@app.get("/api/v1/ecommerce/categories")
async def get_categories():
    return [
        {"id": 1, "name": "Test Category", "product_count": 2}
    ]

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🔧 Python version: {os.sys.version}")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
