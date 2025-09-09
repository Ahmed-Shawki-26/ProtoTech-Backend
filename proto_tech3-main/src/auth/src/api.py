from fastapi import FastAPI
from src.auth.src.auth.controller import router as auth_router
from src.auth.src.users.controller import router as users_router
from src.auth.src.ecommerce.controller import router as ecommerce_router

def register_routes(app: FastAPI):
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(ecommerce_router) # <-- REGISTER

