from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)  # not used as a context manager, so the background scheduler never starts
PHRASE = "every 2nd Tuesday at 6pm until December"


@pytest.fixture(scope="module")
def auth():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    client.post("/register", json={"email": "tester@example.com", "password": "test-only-pw"})
    token = client.post("/token", data={"username": "tester@example.com", "password": "test-only-pw"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def new_task(auth, **fields):
    body = {"title": "Standup", "due_date": "2030-01-01T09:00", "timezone": "Asia/Kolkata", **fields}
    return client.post("/tasks", json=body, headers=auth)


def test_preview_returns_both_readings(auth):
    r = client.post("/tasks/recurrence/preview", json={"text": PHRASE, "timezone": "Asia/Kolkata"}, headers=auth)
    assert r.status_code == 200
    readings = r.json()["interpretations"]
    assert [x["summary"].split(" at ")[0] for x in readings] == [
        "The 2nd Tuesday of every month", "Every other Tuesday"]
    assert readings[0]["occurrences"][0]["label"].endswith("6:00 PM IST")


def test_preview_explains_bad_input(auth):
    r = client.post("/tasks/recurrence/preview", json={"text": "every tuesday at 6", "timezone": "Asia/Kolkata"},
                    headers=auth)
    assert r.status_code == 400
    assert "6am or 6pm" in r.json()["detail"]


def test_preview_requires_login():
    r = client.post("/tasks/recurrence/preview", json={"text": PHRASE, "timezone": "Asia/Kolkata"})
    assert r.status_code == 401


def test_preview_rejects_unknown_time_zone(auth):
    r = client.post("/tasks/recurrence/preview", json={"text": PHRASE, "timezone": "Mars/Olympus"}, headers=auth)
    assert r.status_code == 422


def test_create_uses_chosen_reading_and_server_computed_due_date(auth):
    r = new_task(auth, recurrence_text=PHRASE, recurrence_choice=1)
    assert r.status_code == 200
    task = r.json()
    assert task["recurrence_summary"].startswith("Every other Tuesday at 6:00 PM")
    due = datetime.fromisoformat(task["due_date"])
    assert due.weekday() == 1 and (due.hour, due.minute) == (18, 0)
    assert due > datetime.now()


def test_create_rejects_unparseable_repeat(auth):
    r = new_task(auth, recurrence_text="every blursday")
    assert r.status_code == 400
    assert "blursday" in r.json()["detail"]


def test_completing_a_recurring_task_moves_it_to_the_next_occurrence(auth):
    task = new_task(auth, recurrence_text="every day at 9am").json()
    first_due = datetime.fromisoformat(task["due_date"])
    r = client.patch(f"/tasks/{task['id']}", json={"status": "completed"}, headers=auth)
    updated = r.json()
    assert updated["status"] == "pending"
    assert datetime.fromisoformat(updated["due_date"]) == first_due + timedelta(days=1)
