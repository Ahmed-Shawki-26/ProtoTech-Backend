#!/usr/bin/env python3
"""
Ultra minimal FastAPI app for Railway deployment
This is the most basic possible FastAPI app to ensure it works
"""

import os
import sys

print("🚀 Starting Ultra Minimal FastAPI Server...")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"🐍 Python path: {sys.executable}")
print(f"🔧 Python version: {sys.version}")

try:
    from fastapi import FastAPI
    print("✅ FastAPI imported successfully")
except ImportError as e:
    print(f"❌ Failed to import FastAPI: {e}")
    sys.exit(1)

# Create the simplest possible FastAPI app
app = FastAPI(title="ProtoTech Ultra Minimal API")

@app.get("/")
async def root():
    return {"message": "ProtoTech API is running (Ultra Minimal)", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Ultra minimal health check"}

@app.get("/test")
async def test():
    return {"message": "Test endpoint working", "status": "ok"}

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment
    port = int(os.getenv("PORT", 8000))
    print(f"🌐 Starting server on port {port}")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)
