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
    
    # Use Railway's PORT environment variable or default to 8000
    # Force port 8000 for Railway domain compatibility
    port = 8000
    print(f"🚀 Starting server on port {port} (Railway compatible)")
    
    try:
        # Simple, direct uvicorn startup with minimal app
        uvicorn.run(
            "minimal_main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info",
            access_log=True,
            workers=1
        )
    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        # Exit with error code so Railway knows it failed
        sys.exit(1)
