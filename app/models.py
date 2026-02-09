from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Integer, default=True) # Boolean stored as Integer in SQLite 

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    due_date = Column(DateTime, nullable=False)
    priority = Column(String, default="low")  # high/moderate/low
    user_email = Column(String, nullable=False) # In a real app we'd use ForeignKey("users.email")

    status = Column(String, default="pending")  # pending/completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_reminded_at = Column(DateTime(timezone=True), nullable=True)
    reminders_sent = Column(String, default="")  # Tracks milestones like "60,30,15,5"
