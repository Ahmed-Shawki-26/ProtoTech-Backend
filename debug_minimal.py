#!/usr/bin/env python3
"""
Minimal debug server to test what's causing the 502 errors
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ProtoTech Debug API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://proto-tech-frontend.vercel.app",
        "https://proto-tech-frontend-9aqs0a11r-ahmedshawki2026-3667s-projects.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ],
    allow_origin_regex=r"^https://([a-z0-9-]+\.)?vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Debug server is working"}

@app.get("/test")
async def test():
    return {"message": "Test endpoint working", "status": "ok"}

@app.get("/api/v1/ecommerce/products")
async def test_products():
    return [
        {
            "id": 1,
            "name": "Test Product 1",
            "price": 29.99,
            "description": "This is a test product"
        }
    ]

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting debug server on port 8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
