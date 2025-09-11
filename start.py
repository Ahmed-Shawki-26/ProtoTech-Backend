#!/usr/bin/env python3
import uvicorn
import os
import sys

if __name__ == "__main__":
    # Force port 8000 for Railway domain compatibility
    port = 8000
    print(f"🚀 Starting ProtoTech Backend Server on port {port}")
    print(f"📁 Current working directory: {os.getcwd()}")
    print(f"🐍 Python path: {sys.executable}")
    
    try:
        # Test if main_simple.py can be imported
        print("🔄 Testing main_simple.py import...")
        import main_simple
        print("✅ main_simple.py imported successfully")
        
        # Run the simplified application
        print("🚀 Starting uvicorn server...")
        uvicorn.run(
            "main_simple:app",
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
