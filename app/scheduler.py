import os
import pytz
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Task
from .email_utils import send_email

load_dotenv()

scheduler = BackgroundScheduler()
IST = pytz.timezone('Asia/Kolkata')

def log_to_file(message):
    now_ist = datetime.now(IST)
    with open("scheduler_log.txt", "a") as f:
        f.write(f"[{now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}\n")

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
            task_time = IST.localize(task.due_date)
            
            if task_time <= now_ist:
                log_to_file(f"Triggering IST notification for: '{task.title}' to {task.user_email}")
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
                    log_to_file(f"SUCCESS: Email sent for '{task.title}'.")
                    
                    # Mark as completed
                    task.status = "completed"
                    task.last_reminded_at = now_ist
                    db.commit()
                except Exception as e:
                    log_to_file(f"FAILED for '{task.title}': {e}")
    finally:
        db.close()

def start_scheduler():
    scheduler.add_job(reminder_job, "interval", minutes=1)
    scheduler.start()
