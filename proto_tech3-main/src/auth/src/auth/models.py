from uuid import UUID
from pydantic import BaseModel, EmailStr
from typing import Optional

class RegisterUserRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None # <--- Add refresh_token (optional for response)


class TokenData(BaseModel):
    user_id: str | None = None

    #  this func convrts it into UUID to be able to stored in the db 
    def get_uuid(self) -> UUID | None:
        if self.user_id:
            return UUID(self.user_id)
        return None
