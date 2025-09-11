#!/usr/bin/env python3
"""
Production server startup script
"""

import uvicorn
import os
import sys

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    print("Starting ProtoTech Backend Server (Production Mode)...")
    print("Server will be available at: http://0.0.0.0:8000")
    print("Press Ctrl+C to stop the server")
    
    # Check critical environment variables
    port = int(os.getenv("PORT", 8000))
    environment = os.getenv("ENVIRONMENT", "production")
    
    # Force port 8000 if Railway domain is configured for it
    if os.getenv("RAILWAY_ENVIRONMENT"):
        port = 8000
        print(f"🔄 Railway detected - using port 8000 for domain compatibility")
    
    print(f"🔧 Configuration:")
    print(f"   - Port: {port}")
    print(f"   - Environment: {environment}")
    print(f"   - Python Path: {sys.path[0]}")
    
    # Check if main.py exists and is importable
    try:
        import main
        print("✅ main.py imported successfully")
    except Exception as e:
        print(f"❌ Failed to import main.py: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        print("🚀 Starting uvicorn server...")
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info",
            access_log=True,
            workers=1
        )
    except Exception as e:
        print(f"❌ Server startup error: {e}")
        import traceback
        traceback.print_exc()
        # Keep the process alive for debugging
        import time
        while True:
            print("🔄 Server failed, keeping container alive for debugging...")
            time.sleep(30)
