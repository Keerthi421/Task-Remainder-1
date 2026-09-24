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
        now_ist = datetime.now(IST)
        tasks   = db.query(Task).filter(Task.status == "pending").all()

        for task in tasks:
            # Localise due_date to IST
            try:
                task_time = IST.localize(task.due_date) if task.due_date.tzinfo is None \
                            else task.due_date.astimezone(IST)
            except Exception:
                continue

            minutes_until = (task_time - now_ist).total_seconds() / 60

            # Which milestones should be sent?
            try:
                milestones = [int(m) for m in (task.reminder_minutes or "0").split(",") if m.strip()]
            except Exception:
                milestones = [0]

            sent_set = set(task.reminders_sent.split(",")) if task.reminders_sent else set()

            for milestone in milestones:
                milestone_key = str(milestone)
                if milestone_key in sent_set:
                    continue

                # Fire within a 1-minute window of the milestone time
                if minutes_until <= milestone + 1 and minutes_until > milestone - 1:
                    task_time_str = task_time.strftime("%Y-%m-%d %H:%M:%S IST")
                    now_str       = now_ist.strftime("%Y-%m-%d %H:%M:%S")

                    try:
                        ok = send_reminder_email(task, task_time_str, now_str)
                    except Exception as e:
                        logger.error(f"Email error for '{task.title}': {e}", exc_info=True)
                        ok = False

                    if ok:
                        # Record milestone
                        sent_set.add(milestone_key)
                        task.reminders_sent   = ",".join(sent_set)
                        task.last_reminded_at = now_ist
                        task.retry_count      = 0
                        logger.info(f"Sent {milestone}m reminder for '{task.title}'")

                        # Send SMS if phone is on file
                        profile = db.query(UserProfile).filter_by(user_email=task.user_email).first()
                        if profile and profile.phone:
                            sms_msg = (f"Reminder: {task.title} | "
                                       f"Due: {task_time_str} | Priority: {task.priority}")
                            send_sms(profile.phone, sms_msg)

                        # Mark complete only on the final milestone (0 = at due time)
                        if milestone == 0:
                            task.status = "completed"
                            crud.award_points(db, task.user_email, 10)
                            # Notify assigned_to
                            if task.assigned_to and task.assigned_to != task.user_email:
                                try:
                                    send_reminder_email(
                                        type('T', (), {**task.__dict__,
                                                       'user_email': task.assigned_to})(),
                                        task_time_str, now_str
                                    )
                                except Exception:
                                    pass
                    else:
                        task.retry_count = (task.retry_count or 0) + 1
                        if task.retry_count >= 5:
                            task.status = "completed"  # give up after 5 failures
                            logger.warning(f"Giving up on '{task.title}' after 5 retries")

                    db.commit()

    except Exception as e:
        logger.error(f"reminder_job crashed: {e}", exc_info=True)
    finally:
        db.close()


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
