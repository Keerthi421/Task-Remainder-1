import os
import pytz
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Task
from .email_utils import send_email

import logging
import sys

load_dotenv()

# Configure logging to write to stdout so Render can capture it
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
IST = pytz.timezone('Asia/Kolkata')

def reminder_job():
    db: Session = SessionLocal()
    try:
        now_ist = datetime.now(IST)
        # Find pending tasks
        tasks = db.query(Task).filter(Task.status == "pending").all()
        
        for task in tasks:
            # We assume the user-inputted time in index.html (datetime-local)
            # is meant to be in their local time (IST).
            # SQLite stores it as naive datetime. Let's treat it as IST.
            try:
                task_time = IST.localize(task.due_date)
            except ValueError:
                 # Already tz-aware?
                 task_time = task.due_date.astimezone(IST)
            
            if task_time <= now_ist:
                logger.info(f"Triggering IST notification for: '{task.title}' to {task.user_email}")
                try:
                    subject = f"🔔 Notification: {task.title}"
                    body = f"""
Hello, this is your scheduled reminder for: {task.title}

Priority: {task.priority}
Description:
{task.description}

Scheduled for (IST): {task_time.strftime('%Y-%m-%d %H:%M:%S')}
Sent at (IST): {now_ist.strftime('%Y-%m-%d %H:%M:%S')}
                    """
                    send_email(task.user_email, subject, body)
                    logger.info(f"SUCCESS: Email sent for '{task.title}'.")
                    
                    # Mark as completed
                    task.status = "completed"
                    task.last_reminded_at = now_ist
                    db.commit()
                except Exception as e:
                    logger.error(f"FAILED for '{task.title}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Scheduler Job Failed: {e}", exc_info=True)
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(reminder_job, "interval", minutes=1)
        scheduler.start()
        logger.info("Scheduler started successfully.")
