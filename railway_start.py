#!/usr/bin/env python3
import os, sys, signal, time, traceback
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def handle_term(signum, frame):
    print(f"⚠️ SIGTERM {signum} at {time.time()}", flush=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_term)

print("=== RAILWAY ENVIRONMENT ===")
for k, v in os.environ.items():
    if k.startswith(("RAILWAY", "PORT", "HOST")):
        print(f"{k}={v}")
print("========================", flush=True)

# Try to import your real app
app = None
try:
    from main import app as real_app
    app = real_app
    print("✅ Imported FastAPI app from main", flush=True)
except Exception as e:
    print(f"❌ Failed to import main app: {e}", flush=True)
    traceback.print_exc()
    print("🔄 Falling back to minimal app...", flush=True)
    app = FastAPI(title="ProtoTech API - Fallback")

# ALWAYS add CORS and a guaranteed /health on the final app
allowed_origins = [
    "https://proto-tech-frontend.vercel.app",
    "https://proto-tech-frontend-9aqs0a11r-ahmedshawki2026-3667s-projects.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,   # not "*" when allow_credentials=True
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
async def root():
    return {"status": "ok", "service": "ProtoTech API"}

# Start server
port = int(os.getenv("PORT") or "8080")
print(f"🚀 Starting Uvicorn on 0.0.0.0:{port}", flush=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
