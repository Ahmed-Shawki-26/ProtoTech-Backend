#!/usr/bin/env python3
"""
Simple server startup script
"""

import uvicorn
import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("Starting ProtoTech Backend Server...")
    print("Server will be available at: http://localhost:8000")
    print("Webhook endpoint: http://localhost:8000/api/v1/ecommerce/webhook")
    print("Press Ctrl+C to stop the server")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
