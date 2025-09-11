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
    
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=int(os.getenv("PORT", 8000)),
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
