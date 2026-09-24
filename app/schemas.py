from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import Literal, Any

Priority = Literal["low", "moderate", "high"]
Status   = Literal["pending", "completed"]

# ── Tasks ─────────────────────────────────────────────────────────────────────

class SubTask(BaseModel):
    id:   int
    text: str
    done: bool = False

class TaskCreate(BaseModel):
    title:            str       = Field(min_length=1, max_length=200)
    description:      str       = Field(default="", max_length=2000)
    due_date:         datetime
    priority:         Priority  = "low"
    tags:             str       = Field(default="", max_length=500)   # comma-separated
    reminder_minutes: list[int] = Field(default=[0])                  # e.g. [1440, 60, 0]
    sub_tasks:        list[dict] = Field(default=[])
    assigned_to:      EmailStr | None = None
    user_email:       EmailStr | None = None   # ignored, kept for backward compat

class TaskUpdate(BaseModel):
    title:       str | None      = Field(default=None, min_length=1, max_length=200)
    description: str | None      = Field(default=None, max_length=2000)
    due_date:    datetime | None = None
    priority:    Priority | None = None
    status:      Status | None   = None
    tags:        str | None      = None
    sort_order:  int | None      = None
    sub_tasks:   list[dict] | None = None
    assigned_to: str | None      = None

class TaskOut(BaseModel):
    id:               int
    title:            str
    description:      str
    due_date:         datetime
    priority:         str
    user_email:       EmailStr
    status:           str
    created_at:       datetime
    last_reminded_at: datetime | None = None
    tags:             str       = ""
    sort_order:       int       = 0
    reminder_minutes: str       = "0"
    sub_tasks:        str       = "[]"
    retry_count:      int       = 0
    public_token:     str | None = None
    assigned_to:      str | None = None

    class Config:
        from_attributes = True

# ── Templates ─────────────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name:             str       = Field(min_length=1, max_length=100)
    title:            str       = Field(min_length=1, max_length=200)
    description:      str       = ""
    priority:         Priority  = "low"
    tags:             str       = ""
    reminder_minutes: list[int] = [0]
    sub_tasks:        list[dict] = []

class TemplateOut(BaseModel):
    id:               int
    name:             str
    title:            str
    description:      str
    priority:         str
    tags:             str
    reminder_minutes: str
    sub_tasks:        str
    created_at:       datetime

    class Config:
        from_attributes = True

# ── User / Auth ───────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email:    EmailStr
    password: str = Field(min_length=6, max_length=128)

class UserOut(BaseModel):
    id:        int
    email:     EmailStr
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type:   str

class TokenData(BaseModel):
    email: str | None = None

# ── Profile / Stats ───────────────────────────────────────────────────────────

class ProfileOut(BaseModel):
    points:                int
    level:                 int
    level_name:            str
    streak_days:           int
    weekly_digest_enabled: bool
    phone:                 str | None = None

class ProfileUpdate(BaseModel):
    weekly_digest_enabled: bool | None = None
    phone:                 str | None  = None

class StatsOut(BaseModel):
    total:           int
    pending:         int
    completed_today: int
    overdue:         int
    streak:          int
    points:          int
    level:           int
    level_name:      str

# ── AI / Import ───────────────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

class PriorityRequest(BaseModel):
    title:       str
    description: str = ""

class ReorderItem(BaseModel):
    id:         int
    sort_order: int
