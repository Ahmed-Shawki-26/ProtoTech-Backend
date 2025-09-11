#!/usr/bin/env python3
"""
Railway production FastAPI app
Uses the real ProtoTech FastAPI application with all endpoints
"""

import os
import sys
import signal
import time
import uvicorn

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

# Import the real FastAPI application
try:
    from main import app
    print("✅ Successfully imported main FastAPI application")
except ImportError as e:
    print(f"❌ Failed to import main application: {e}")
    print("🔄 Falling back to minimal test server...")
    
    # Fallback to minimal server if import fails
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(title="ProtoTech API - Railway Fallback")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        return {"status": "ok", "message": "ProtoTech API fallback is running"}
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "message": "Health check working"}

# Ensure we're getting the port correctly
port = int(os.getenv("PORT", 8000))
print(f"🔍 PORT environment variable: {os.getenv('PORT', 'NOT SET')}")
print(f"🚀 Starting server on 0.0.0.0:{port}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
