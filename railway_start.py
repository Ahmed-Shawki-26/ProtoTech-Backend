#!/usr/bin/env python3
"""
Railway debugging FastAPI app
Comprehensive debugging to identify Railway routing issues
"""

import os
import sys
import signal
import time
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Add SIGTERM handler to detect platform shutdowns
def handle_term(signum, frame):
    print(f"⚠️ Received signal {signum} (SIGTERM) from platform at {time.time()}")
    print("Platform is shutting down the container")
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_term)

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
    return {"status": "ok", "port": port, "message": "Health check working"}

@app.on_event("startup")
async def startup_event():
    print("✅ FastAPI application startup completed successfully")
    print("🔗 Health check endpoint available at: /health")
    print("🔗 Root endpoint available at: /")
    print("🔗 Debug endpoint available at: /debug/railway")

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

# Procfile will handle running the server
# No need for if __name__ == "__main__" block
