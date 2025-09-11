#!/usr/bin/env python3
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}")
    
    # Run the minimal app directly
    uvicorn.run(
        "minimal_main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
