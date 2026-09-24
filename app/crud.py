import json
import secrets
from datetime import datetime, date
from sqlalchemy.orm import Session
from . import models, schemas
from .auth import get_password_hash
import pytz

IST = pytz.timezone('Asia/Kolkata')

# ── Helpers ───────────────────────────────────────────────────────────────────

LEVEL_THRESHOLDS = [0, 100, 300, 600, 1000, 2000]
LEVEL_NAMES      = {1: "Starter", 2: "Consistent", 3: "Focused",
                    4: "Productive", 5: "Expert", 6: "Master"}

def _compute_level(points: int) -> int:
    for lvl, threshold in enumerate(reversed(LEVEL_THRESHOLDS), 1):
        if points >= threshold:
            return len(LEVEL_THRESHOLDS) - lvl + 1
    return 1

def _rm_to_str(rm: list[int]) -> str:
    return ",".join(str(m) for m in rm) if rm else "0"

def _rm_to_list(rm_str: str) -> list[int]:
    try:
        return [int(x) for x in rm_str.split(",") if x.strip()]
    except Exception:
        return [0]

# ── Users ─────────────────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_count(db: Session) -> int:
    return db.query(models.User).count()

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(email=user.email, hashed_password=get_password_hash(user.password))
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# ── Profile ───────────────────────────────────────────────────────────────────

def get_or_create_profile(db: Session, email: str) -> models.UserProfile:
    profile = db.query(models.UserProfile).filter_by(user_email=email).first()
    if not profile:
        profile = models.UserProfile(user_email=email)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

def award_points(db: Session, email: str, pts: int) -> models.UserProfile:
    profile = get_or_create_profile(db, email)
    profile.points += pts
    profile.level   = _compute_level(profile.points)
    today = datetime.now(IST).date()
    if profile.last_completion_date:
        diff = (today - profile.last_completion_date).days
        if diff == 0:
            pass
        elif diff == 1:
            profile.streak_days += 1
        else:
            profile.streak_days = 1
    else:
        profile.streak_days = 1
    profile.last_completion_date = today
    db.commit()
    db.refresh(profile)
    return profile

def get_profile_out(db: Session, email: str) -> schemas.ProfileOut:
    p = get_or_create_profile(db, email)
    return schemas.ProfileOut(
        points=p.points, level=p.level,
        level_name=LEVEL_NAMES.get(p.level, "Starter"),
        streak_days=p.streak_days,
        weekly_digest_enabled=bool(p.weekly_digest_enabled),
        phone=p.phone
    )

def update_profile(db: Session, email: str, upd: schemas.ProfileUpdate) -> schemas.ProfileOut:
    profile = get_or_create_profile(db, email)
    if upd.weekly_digest_enabled is not None:
        profile.weekly_digest_enabled = int(upd.weekly_digest_enabled)
    if upd.phone is not None:
        profile.phone = upd.phone or None
    db.commit()
    return get_profile_out(db, email)

# ── Tasks ─────────────────────────────────────────────────────────────────────

def create_task(db: Session, task: schemas.TaskCreate, user_email: str) -> models.Task:
    db_task = models.Task(
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        priority=task.priority,
        user_email=user_email,
        tags=task.tags,
        reminder_minutes=_rm_to_str(task.reminder_minutes),
        sub_tasks=json.dumps(task.sub_tasks),
        assigned_to=task.assigned_to,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_tasks(db: Session, user_email: str) -> list[models.Task]:
    return (db.query(models.Task)
              .filter(models.Task.user_email == user_email)
              .order_by(models.Task.sort_order, models.Task.due_date)
              .all())

def get_task(db: Session, task_id: int, user_email: str) -> models.Task | None:
    return db.query(models.Task).filter(
        models.Task.id == task_id, models.Task.user_email == user_email
    ).first()

def get_task_by_public_token(db: Session, token: str) -> models.Task | None:
    return db.query(models.Task).filter(models.Task.public_token == token).first()

def update_task(db: Session, task_id: int, upd: schemas.TaskUpdate,
                user_email: str) -> models.Task | None:
    task = get_task(db, task_id, user_email)
    if not task:
        return None
    data = upd.model_dump(exclude_unset=True)
    if "sub_tasks" in data and isinstance(data["sub_tasks"], list):
        data["sub_tasks"] = json.dumps(data["sub_tasks"])
    was_pending = task.status == "pending"
    for k, v in data.items():
        setattr(task, k, v)
    # Award points when marked complete
    if was_pending and task.status == "completed":
        award_points(db, user_email, 10)
    db.commit()
    db.refresh(task)
    return task

def delete_task(db: Session, task_id: int, user_email: str) -> bool:
    task = get_task(db, task_id, user_email)
    if not task:
        return False
    db.delete(task)
    db.commit()
    return True

def reorder_tasks(db: Session, items: list[schemas.ReorderItem], user_email: str):
    for item in items:
        task = get_task(db, item.id, user_email)
        if task:
            task.sort_order = item.sort_order
    db.commit()

def generate_public_token(db: Session, task_id: int, user_email: str) -> models.Task | None:
    task = get_task(db, task_id, user_email)
    if not task:
        return None
    if not task.public_token:
        task.public_token = secrets.token_urlsafe(16)
        db.commit()
        db.refresh(task)
    return task

# ── Templates ─────────────────────────────────────────────────────────────────

def create_template(db: Session, tmpl: schemas.TemplateCreate, user_email: str):
    db_tmpl = models.TaskTemplate(
        user_email=user_email,
        name=tmpl.name,
        title=tmpl.title,
        description=tmpl.description,
        priority=tmpl.priority,
        tags=tmpl.tags,
        reminder_minutes=_rm_to_str(tmpl.reminder_minutes),
        sub_tasks=json.dumps(tmpl.sub_tasks),
    )
    db.add(db_tmpl)
    db.commit()
    db.refresh(db_tmpl)
    return db_tmpl

def get_templates(db: Session, user_email: str):
    return db.query(models.TaskTemplate).filter_by(user_email=user_email).all()

def delete_template(db: Session, tmpl_id: int, user_email: str) -> bool:
    tmpl = db.query(models.TaskTemplate).filter(
        models.TaskTemplate.id == tmpl_id,
        models.TaskTemplate.user_email == user_email
    ).first()
    if not tmpl:
        return False
    db.delete(tmpl)
    db.commit()
    return True

# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats(db: Session, user_email: str) -> schemas.StatsOut:
    from datetime import timedelta
    now_ist = datetime.now(IST)
    today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)

    tasks = get_tasks(db, user_email)
    total           = len(tasks)
    pending         = sum(1 for t in tasks if t.status == "pending")
    completed_today = sum(
        1 for t in tasks
        if t.status == "completed" and t.last_reminded_at
        and t.last_reminded_at.replace(tzinfo=IST if t.last_reminded_at.tzinfo is None else None) >= today_start
    )
    overdue = sum(
        1 for t in tasks
        if t.status == "pending" and
        (IST.localize(t.due_date) if t.due_date.tzinfo is None else t.due_date.astimezone(IST)) < now_ist
    )
    p = get_or_create_profile(db, user_email)
    return schemas.StatsOut(
        total=total, pending=pending,
        completed_today=completed_today, overdue=overdue,
        streak=p.streak_days, points=p.points,
        level=p.level, level_name=LEVEL_NAMES.get(p.level, "Starter")
    )
