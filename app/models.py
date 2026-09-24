from sqlalchemy import Column, Integer, String, DateTime, Text, Date
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"
    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String, unique=True, index=True)
    hashed_password= Column(String)
    is_active      = Column(Integer, default=True)


class Task(Base):
    __tablename__ = "tasks"
    id               = Column(Integer, primary_key=True, index=True)
    title            = Column(String, nullable=False)
    description      = Column(String, default="")
    due_date         = Column(DateTime, nullable=False)
    priority         = Column(String, default="low")       # low|moderate|high
    user_email       = Column(String, nullable=False)
    status           = Column(String, default="pending")   # pending|completed
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    last_reminded_at = Column(DateTime(timezone=True), nullable=True)
    reminders_sent   = Column(String, default="")          # "1440,60" – milestones already sent
    # ── New columns ────────────────────────────────────────────
    tags             = Column(String, default="")          # comma-separated tags
    sort_order       = Column(Integer, default=0)
    reminder_minutes = Column(String, default="0")         # "1440,60,0" – milestones to send
    sub_tasks        = Column(Text,   default="[]")        # JSON array {id,text,done}
    retry_count      = Column(Integer, default=0)
    public_token     = Column(String, nullable=True, unique=True, index=True)
    assigned_to      = Column(String, nullable=True)       # extra email for shared tasks


class TaskTemplate(Base):
    __tablename__ = "task_templates"
    id               = Column(Integer, primary_key=True, index=True)
    user_email       = Column(String, nullable=False, index=True)
    name             = Column(String, nullable=False)
    title            = Column(String, nullable=False)
    description      = Column(String, default="")
    priority         = Column(String, default="low")
    tags             = Column(String, default="")
    reminder_minutes = Column(String, default="0")
    sub_tasks        = Column(Text,   default="[]")
    created_at       = Column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id                    = Column(Integer, primary_key=True, index=True)
    user_email            = Column(String, unique=True, nullable=False, index=True)
    points                = Column(Integer, default=0)
    level                 = Column(Integer, default=1)
    streak_days           = Column(Integer, default=0)
    last_completion_date  = Column(Date, nullable=True)
    weekly_digest_enabled = Column(Integer, default=1)   # boolean
    phone                 = Column(String, nullable=True) # for SMS (Twilio)
