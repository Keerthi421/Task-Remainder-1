import os
import sys
import pytz
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Task, User, UserProfile
from .email_utils import send_reminder_email, send_weekly_digest, send_sms
from .recurrence import get_tz, localize
from . import crud

load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
IST = pytz.timezone('Asia/Kolkata')


# ── Main reminder job (runs every minute) ──────────────────────────────────────

def reminder_job():
    db: Session = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.status == "pending").all()
        for task in tasks:
            try:
                _process_task(db, task)
            except Exception as e:
                db.rollback()
                logger.error(f"Reminder failed for task {task.id}: {e}", exc_info=True)
    finally:
        db.close()


def _process_task(db: Session, task: Task):
    tz = get_tz(task.timezone)
    now_local = datetime.now(tz)
    task_time = (localize(task.due_date, tz) if task.due_date.tzinfo is None
                 else task.due_date.astimezone(tz))
    minutes_until = (task_time - now_local).total_seconds() / 60

    try:
        milestones = sorted({int(m) for m in (task.reminder_minutes or "0").split(",") if m.strip()},
                            reverse=True)
    except ValueError:
        milestones = [0]
    sent_set = set(task.reminders_sent.split(",")) if task.reminders_sent else set()
    task_time_str = task_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    now_str = now_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    notify_to = task.notification_email or task.user_email

    for milestone in milestones:
        if str(milestone) in sent_set:
            continue
        # Fire within a 1-minute window of the milestone time
        if not (milestone - 1 < minutes_until <= milestone + 1):
            continue

        try:
            ok = send_reminder_email(task, task_time_str, now_str, override_email=notify_to)
        except Exception as e:
            logger.error(f"Email error for '{task.title}': {e}", exc_info=True)
            ok = False

        if not ok:
            task.retry_count = (task.retry_count or 0) + 1
            if task.retry_count >= 5:
                logger.warning(f"Giving up on this occurrence of '{task.title}' after 5 retries")
                if task.recurrence_rule:
                    crud.advance_recurring(task, after=task.due_date)
                else:
                    task.status = "completed"
            db.commit()
            return

        sent_set.add(str(milestone))
        task.reminders_sent = ",".join(sent_set)
        task.last_reminded_at = now_local
        task.retry_count = 0
        logger.info(f"Sent {milestone}m reminder for '{task.title}' to {notify_to}")

        profile = db.query(UserProfile).filter_by(user_email=task.user_email).first()
        if profile and profile.phone:
            send_sms(profile.phone, f"Reminder: {task.title} | Due: {task_time_str} | Priority: {task.priority}")

        if milestone == 0:
            if task.assigned_to and task.assigned_to != notify_to:
                try:
                    send_reminder_email(task, task_time_str, now_str, override_email=task.assigned_to)
                except Exception as e:
                    logger.error(f"Assignee email error for '{task.title}': {e}")
            if task.recurrence_rule:
                crud.advance_recurring(task, after=task.due_date)
            else:
                task.status = "completed"
                crud.award_points(db, task.user_email, 10)
            db.commit()
            return
        db.commit()

    # A recurring occurrence that passed without its deadline reminder (server was down, or no
    # "at deadline" step) moves on to the next future occurrence instead of stalling.
    if task.recurrence_rule and minutes_until <= -1:
        skipped_to = max(task.due_date, now_local.replace(tzinfo=None))
        if crud.advance_recurring(task, after=skipped_to):
            logger.info(f"'{task.title}' moved to next occurrence {task.due_date}")
        db.commit()


# ── Weekly digest (every Monday 08:00 IST) ────────────────────────────────────

def weekly_digest_job():
    db: Session = SessionLocal()
    try:
        now_ist       = datetime.now(IST)
        week_ago      = now_ist - timedelta(days=7)
        week_from_now = now_ist + timedelta(days=7)

        users = db.query(User).filter(User.is_active == 1).all()
        for user in users:
            profile = db.query(UserProfile).filter_by(user_email=user.email).first()
            if profile and not profile.weekly_digest_enabled:
                continue

            completed = db.query(Task).filter(
                Task.user_email == user.email,
                Task.status     == "completed",
                Task.last_reminded_at >= week_ago
            ).all()

            upcoming = db.query(Task).filter(
                Task.user_email == user.email,
                Task.status     == "pending",
                Task.due_date   <= week_from_now,
                Task.due_date   >= now_ist
            ).all()

            if not completed and not upcoming:
                continue

            send_weekly_digest(user.email, completed, upcoming)
            logger.info(f"Weekly digest sent to {user.email}")

    except Exception as e:
        logger.error(f"weekly_digest_job crashed: {e}", exc_info=True)
    finally:
        db.close()


# ── Startup ───────────────────────────────────────────────────────────────────

def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(reminder_job, "interval", minutes=1, id="reminder")
    scheduler.add_job(
        weekly_digest_job, "cron",
        day_of_week="mon", hour=8, minute=0,
        timezone=IST, id="weekly_digest"
    )
    scheduler.start()
    logger.info("Scheduler started (reminder every 1 min, digest every Monday 08:00 IST).")
