from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reminder.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations(eng):
    """Add new columns to existing tables without losing data."""
    new_task_cols = [
        ("tags",             "TEXT    DEFAULT ''"),
        ("sort_order",       "INTEGER DEFAULT 0"),
        ("reminder_minutes", "TEXT    DEFAULT '0'"),
        ("sub_tasks",        "TEXT    DEFAULT '[]'"),
        ("retry_count",      "INTEGER DEFAULT 0"),
        ("public_token",     "TEXT"),
        ("assigned_to",      "TEXT"),
    ]
    with eng.connect() as conn:
        for col, definition in new_task_cols:
            try:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col} {definition}"))
                conn.commit()
            except Exception:
                pass  # column already exists
