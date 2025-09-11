#!/usr/bin/env python3
"""
Ultra minimal start script for Railway
"""

import os
import sys
import uvicorn

print("🚀 Starting Ultra Minimal Server for Railway...")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"🐍 Python path: {sys.executable}")

# Get port from environment
port = int(os.getenv("PORT", 8000))
print(f"🌐 Starting server on port {port}")

try:
    # Import the ultra minimal app
    from ultra_minimal import app
    print("✅ Successfully imported ultra_minimal app")
    
    # Start the server
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info",
        access_log=True
    )
except Exception as e:
    print(f"❌ Failed to start ultra minimal server: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
