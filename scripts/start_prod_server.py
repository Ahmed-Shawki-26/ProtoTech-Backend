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
    print("Starting minimal FastAPI server...")
    
    # Use Railway's PORT environment variable
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting server on port {port}")
    
    try:
        # Import and run the minimal app directly
        from minimal_main import app
        uvicorn.run(app, host="0.0.0.0", port=port)
    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
