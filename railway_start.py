#!/usr/bin/env python3
"""
Railway debugging FastAPI app
Comprehensive debugging to identify Railway routing issues
"""

import os
import sys
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Debug: Print all Railway environment variables
print("=== RAILWAY ENVIRONMENT ===")
for key, value in os.environ.items():
    if key.startswith(('RAILWAY', 'PORT', 'HOST')):
        print(f"{key}={value}")
print("========================")

# Ensure we're getting the port correctly
port = int(os.getenv("PORT", 8000))
print(f"🔍 PORT environment variable: {os.getenv('PORT', 'NOT SET')}")
print(f"🚀 Starting server on 0.0.0.0:{port}")

app = FastAPI(title="ProtoTech API - Railway Debug")

# Temporarily allow all origins for debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporarily allow all for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root(request: Request):
    return {
        "status": "ok",
        "message": "ProtoTech API is running",
        "port": port,
        "headers": dict(request.headers),
        "client": f"{request.client.host}:{request.client.port}" if request.client else "unknown"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "port": port}

@app.get("/debug/railway")
async def debug_railway():
    return {
        "environment": {
            "PORT": os.getenv("PORT"),
            "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT"),
            "RAILWAY_PROJECT_ID": os.getenv("RAILWAY_PROJECT_ID"),
            "RAILWAY_SERVICE_ID": os.getenv("RAILWAY_SERVICE_ID"),
            "RAILWAY_DEPLOYMENT_ID": os.getenv("RAILWAY_DEPLOYMENT_ID"),
        },
        "server_info": {
            "host": "0.0.0.0",
            "port": port,
            "pid": os.getpid(),
        }
    }

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
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🔧 Python version: {sys.version}")
    print(f"🌐 Binding to ALL interfaces (0.0.0.0) - CRITICAL for Railway")
    
    # Force unbuffered output
    sys.stdout.flush()
    
    try:
        # CRITICAL: Must bind to 0.0.0.0, not 127.0.0.1 or localhost
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug", access_log=True)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
