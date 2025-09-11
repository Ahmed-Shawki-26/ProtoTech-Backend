#!/usr/bin/env python3
"""
Ultra simple FastAPI app for Railway deployment
This is the absolute minimum needed to get Railway working
"""

from fastapi import FastAPI
import uvicorn
import os

# Create FastAPI app
app = FastAPI(title="ProtoTech API")

@app.get("/")
async def root():
    return {"message": "ProtoTech API is running", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Health check passed"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
