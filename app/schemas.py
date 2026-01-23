from pydantic import BaseModel, EmailStr
from datetime import datetime

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    due_date: datetime
    priority: str = "low"
    user_email: EmailStr

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
