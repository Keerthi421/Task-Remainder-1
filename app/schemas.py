from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal

Priority = Literal["low", "moderate", "high"]
Status = Literal["pending", "completed"]

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    due_date: datetime
    priority: Priority = "low"
    # Ignored by the API: reminders always go to the logged-in user's email.
    # Kept optional for backward compatibility with older clients.
    user_email: EmailStr | None = None

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: datetime | None = None
    priority: Priority | None = None
    status: Status | None = None

class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    due_date: datetime
    priority: str
    user_email: EmailStr
    status: str
    created_at: datetime
    last_reminded_at: datetime | None = None

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

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
