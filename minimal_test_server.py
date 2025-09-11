#!/usr/bin/env python3
"""
Minimal test server for Railway debugging
This uses Python's built-in HTTP server to test Railway routing
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import signal
import sys
import json

# Add SIGTERM handler to detect platform shutdowns
def handle_term(signum, frame):
    print(f"⚠️ Received signal {signum} (SIGTERM) from platform at {time.time()}")
    print("Platform is shutting down the container")
    sys.stdout.flush()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_term)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Add CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        response = {
            "status": "ok",
            "message": "Minimal test server working",
            "port": port,
            "path": self.path,
            "method": self.command,
            "time": time.time()
        }
        
        self.wfile.write(json.dumps(response, indent=2).encode())
    
    def do_OPTIONS(self):
        # Handle preflight requests
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    print(f'🚀 Starting minimal test server on 0.0.0.0:{port}')
    print(f'🔍 PORT environment variable: {os.getenv("PORT", "NOT SET")}')
    print(f'🌐 Binding to 0.0.0.0:{port}')
    
    try:
        server = HTTPServer(('0.0.0.0', port), Handler)
        print(f'✅ Server started successfully on 0.0.0.0:{port}')
        server.serve_forever()
    except Exception as e:
        print(f'❌ Error starting server: {e}')
        import traceback
        traceback.print_exc()
