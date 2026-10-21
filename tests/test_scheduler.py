from datetime import timedelta

import pytest
from dateutil.rrule import DAILY, rrule

from app import recurrence, scheduler
from app.database import Base, SessionLocal, engine
from app.models import Task


@pytest.fixture(autouse=True)
def sent(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    outbox = []

    def fake_send(task, task_time_str, now_str, override_email=None):
        outbox.append(override_email)
        return True

    monkeypatch.setattr(scheduler, "send_reminder_email", fake_send)
    monkeypatch.setattr(scheduler, "send_sms", lambda *a: True)
    return outbox


def now_local(tz="Asia/Kolkata"):
    return recurrence.now_in(recurrence.get_tz(tz))


def add_task(due, rule=None, tz="Asia/Kolkata", **extra):
    with SessionLocal() as db:
        t = Task(title="T", due_date=due, user_email="owner@example.com", timezone=tz,
                 recurrence_rule=rule, reminder_minutes="0", **extra)
        db.add(t)
        db.commit()
        return t.id


def get_task(task_id):
    with SessionLocal() as db:
        return db.get(Task, task_id)


def daily_from(due, **kw):
    return str(rrule(DAILY, dtstart=due, **kw))


def test_recurring_task_fires_then_moves_to_next_occurrence(sent):
    due = now_local() + timedelta(seconds=30)
    task_id = add_task(due, daily_from(due))
    scheduler.reminder_job()
    task = get_task(task_id)
    assert sent == ["owner@example.com"]
    assert (task.status, task.due_date, task.reminders_sent) == ("pending", due + timedelta(days=1), "")


def test_reminder_goes_to_notification_email(sent):
    due = now_local() + timedelta(seconds=30)
    add_task(due, notification_email="inbox@example.com")
    scheduler.reminder_job()
    assert sent == ["inbox@example.com"]


def test_missed_occurrence_skips_ahead_without_sending(sent):
    due = now_local() - timedelta(days=3)
    task_id = add_task(due, daily_from(due))
    scheduler.reminder_job()
    task = get_task(task_id)
    assert sent == []
    assert task.status == "pending"
    assert timedelta(0) < task.due_date - now_local() <= timedelta(days=1)


def test_series_completes_after_last_occurrence(sent):
    due = now_local() + timedelta(seconds=30)
    task_id = add_task(due, daily_from(due, count=1))
    scheduler.reminder_job()
    assert get_task(task_id).status == "completed"


def test_one_off_task_completes_after_firing(sent):
    due = now_local() + timedelta(seconds=30)
    task_id = add_task(due)
    scheduler.reminder_job()
    assert sent == ["owner@example.com"]
    assert get_task(task_id).status == "completed"


def test_due_time_is_read_in_the_tasks_own_time_zone(sent):
    due_ny = now_local("America/New_York") + timedelta(seconds=30)
    ny_id = add_task(due_ny, tz="America/New_York")
    ist_id = add_task(due_ny, tz="Asia/Kolkata")  # same wall time, but hours away in IST
    scheduler.reminder_job()
    assert sent == ["owner@example.com"]
    assert get_task(ny_id).status == "completed"
    assert get_task(ist_id).status == "pending"
