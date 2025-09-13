# /src/users/controller.py
from fastapi import APIRouter, status
from uuid import UUID
from src.auth.src.database.core import DbSession
from src.auth.src.users import models
from src.auth.src.users import service
from src.auth.src.auth.service import CurrentUser

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=models.UserResponse)
def get_current_user(current_user: CurrentUser, db: DbSession):
    return service.get_user_by_id(db, current_user.get_uuid())

# # FIX: Uncommented this endpoint to make it active
# @router.put("/change-password", status_code=status.HTTP_200_OK)
# def change_password(
#     password_change: models.PasswordChange, db: DbSession, current_user: CurrentUser
# ):
#     service.change_password(db, current_user.get_uuid(), password_change)
#     return {"message": "Password changed successfully"}