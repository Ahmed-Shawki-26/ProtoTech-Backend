from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

# Add startup logging
print("🚀 Starting ProtoTech Minimal Backend Server...")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"🐍 Python path: {sys.executable}")
print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")

app = FastAPI(
    title="ProtoTech Manufacturing API (Minimal)",
    description="Minimal manufacturing platform for Railway deployment",
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
    print("✅ FastAPI minimal application startup completed successfully")
    print("🔗 Health check endpoint available at: /health")
    print("🔗 Root endpoint available at: /")

@app.get("/")
async def root():
    return {
        "message": "ProtoTech API is running (Minimal Mode)", 
        "status": "ok",
        "version": "2.0.0",
        "environment": os.getenv('ENVIRONMENT', 'development')
    }

@app.get("/health")
async def health():
    """Health check endpoint for Railway"""
    try:
        return {
            "status": "ok", 
            "message": "ProtoTech API is healthy (Minimal Mode)",
            "environment": os.getenv('ENVIRONMENT', 'development'),
            "version": "2.0.0"
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Health check failed: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
