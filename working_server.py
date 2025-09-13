#!/usr/bin/env python3
"""
Working FastAPI server with CORS and basic auth endpoints
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

print("🚀 Starting Working FastAPI Server...")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"🐍 Python path: {sys.executable}")

# Create FastAPI app
app = FastAPI(
    title="ProtoTech Working API",
    description="Working API with CORS and auth endpoints",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Pydantic models
class LoginRequest(BaseModel):
    username: str = None
    password: str = None
    email: str = None  # Allow email as alternative to username

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

# Mock data
mock_user = {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com"
}

# Basic endpoints
@app.get("/")
async def root():
    return {"message": "ProtoTech API is running", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Working server health check"}

@app.get("/test")
async def test():
    return {"message": "Test endpoint working", "status": "ok"}

# Auth endpoints
@app.post("/api/v1/auth/token", response_model=TokenResponse)
async def login(
    username: str = Form(None),
    password: str = Form(None),
    email: str = Form(None)
):
    """Login endpoint - handles both FormData and JSON"""
    # Mock authentication - accept any username/password for testing
    # Handle both username and email fields from FormData
    identifier = username or email
    if identifier and password:
        return TokenResponse(access_token="mock-jwt-token", token_type="bearer")
    else:
        raise HTTPException(status_code=400, detail="Invalid credentials")

@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user endpoint"""
    # Mock user data - return user if token exists
    if credentials and credentials.credentials:
        return UserResponse(**mock_user)
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")

# PCB endpoints (basic)
@app.get("/api/v1/pcb/categories")
async def get_pcb_categories():
    """Get PCB categories"""
    return [
        {"id": 1, "name": "Single Layer", "description": "Basic single layer PCBs"},
        {"id": 2, "name": "Double Layer", "description": "Double sided PCBs"},
        {"id": 3, "name": "Multi Layer", "description": "Complex multi-layer PCBs"}
    ]

@app.get("/api/v1/ecommerce/categories")
async def get_ecommerce_categories():
    """Get e-commerce categories"""
    return [
        {"id": 1, "name": "Electronics", "description": "Electronic components"},
        {"id": 2, "name": "PCBs", "description": "Printed Circuit Boards"},
        {"id": 3, "name": "3D Printing", "description": "3D printed parts"}
    ]

@app.get("/api/v1/ecommerce/products")
async def get_ecommerce_products(limit: int = 20, offset: int = 0):
    """Get e-commerce products"""
    # Mock products data
    products = [
        {"id": 1, "name": "Arduino Uno", "price": 25.99, "category_id": 1},
        {"id": 2, "name": "Raspberry Pi 4", "price": 75.00, "category_id": 1},
        {"id": 3, "name": "Custom PCB", "price": 15.50, "category_id": 2},
        {"id": 4, "name": "3D Printed Case", "price": 12.99, "category_id": 3}
    ]
    return {
        "products": products[offset:offset+limit],
        "total": len(products),
        "limit": limit,
        "offset": offset
    }

@app.get("/api/v1/auth/google/login")
async def google_login(next_url: str = "/"):
    """Google OAuth login endpoint"""
    # Mock Google OAuth - redirect to frontend
    return {"message": "Google OAuth not implemented", "redirect_url": next_url}

@app.get("/favicon.ico")
async def favicon():
    """Favicon endpoint"""
    return {"message": "No favicon available"}

if __name__ == "__main__":
    # Get port from environment
    port = int(os.getenv("PORT", 8000))
    print(f"🌐 Starting server on port {port}")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)
