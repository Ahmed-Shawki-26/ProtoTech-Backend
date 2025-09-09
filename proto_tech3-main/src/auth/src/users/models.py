from pydantic import BaseModel, EmailStr, ConfigDict # <--- Add ConfigDict
from uuid import UUID
from datetime import datetime


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    auth_provider: str         # <--- ADD THIS
    created_at: datetime       # <--- ADD THIS

    # Add ConfigDict to allow mapping from the SQLAlchemy model
    model_config = ConfigDict(from_attributes=True)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    new_password_confirm: str
