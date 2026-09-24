from sqlalchemy.orm import Session
from . import models, schemas
from .auth import get_password_hash
from datetime import datetime

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_count(db: Session):
    return db.query(models.User).count()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_task(db: Session, task: schemas.TaskCreate, user_email: str):
    # Always use the logged-in user's email, never the user_email field from the request
    db_task = models.Task(
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        priority=task.priority,
        user_email=user_email
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_tasks(db: Session, user_email: str):
    """Get all tasks owned by this user."""
    return db.query(models.Task).filter(models.Task.user_email == user_email).all()

def get_task(db: Session, task_id: int, user_email: str):
    """Get a task if it belongs to this user."""
    return db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.user_email == user_email
    ).first()

def update_task(db: Session, task_id: int, upd: schemas.TaskUpdate, user_email: str):
    """Update a task if it belongs to this user."""
    task = get_task(db, task_id, user_email)
    if not task:
        return None
    for k, v in upd.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return task

def delete_task(db: Session, task_id: int, user_email: str):
    """Delete a task if it belongs to this user."""
    task = get_task(db, task_id, user_email)
    if not task:
        return False
    db.delete(task)
    db.commit()
    return True
