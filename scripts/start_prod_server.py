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
    print("🚀 Starting minimal FastAPI server for production...")
    print(f"📁 Current working directory: {os.getcwd()}")
    print(f"🐍 Python path: {sys.executable}")
    print(f"🔧 Python version: {sys.version}")
    
    # Use Railway's PORT environment variable with better error handling
    try:
        port = int(os.getenv("PORT", 8000))
        print(f"🌐 Starting server on port {port}")
    except (ValueError, TypeError) as e:
        print(f"⚠️ Invalid PORT environment variable, using default 8000: {e}")
        port = 8000
    
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    
    # Test basic imports first
    try:
        print("🧪 Testing basic imports...")
        import fastapi
        import uvicorn
        print(f"✅ FastAPI version: {fastapi.__version__}")
        print(f"✅ Uvicorn version: {uvicorn.__version__}")
    except ImportError as e:
        print(f"❌ Missing required dependency: {e}")
        sys.exit(1)
    
    try:
        # Import and run the minimal app directly
        print("📦 Importing minimal_main module...")
        from minimal_main import app
        print("✅ Successfully imported minimal_main module")
        
        print("🚀 Starting uvicorn server...")
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=port,
            log_level="info",
            access_log=True,
            reload=False
        )
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("🔄 Trying alternative import...")
        try:
            # Try importing from the current directory
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from minimal_main import app
            print("✅ Successfully imported minimal_main module (alternative path)")
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="info", reload=False)
        except Exception as e2:
            print(f"❌ Alternative import failed: {e2}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
