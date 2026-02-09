from pydantic import BaseModel, EmailStr
from datetime import datetime

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    due_date: datetime
    priority: str = "low"
    # user_email is now optional here as we'll get it from token, 
    # but good to keep optional for backward compatibility or admin
    user_email: EmailStr | None = None 

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    priority: str | None = None
    status: str | None = None

class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    due_date: datetime
    priority: str
    user_email: EmailStr
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None
