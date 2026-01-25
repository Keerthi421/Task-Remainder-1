from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .database import Base, engine, get_db
from . import crud, schemas
from .scheduler import start_scheduler

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Deadline Reminder Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def read_root():
    return FileResponse("frontend/index.html")

@app.on_event("startup")
def startup():
    print("LOG: FastAPI Startup logic executing...")
    start_scheduler()
    print("LOG: Scheduler started successfully.")

@app.get("/scheduler-status")
def scheduler_status():
    from .scheduler import scheduler
    return {
        "is_running": scheduler.running,
        "mode": "Simple Scheduled Notification",
        "jobs": [str(j) for j in scheduler.get_jobs()]
    }

@app.post("/test-email")
def test_email(to_email: str):
    from .email_utils import send_email
    try:
        send_email(to_email, "Test Email from Task Reminder", "If you see this, your SMTP settings are correct! 🚀")
        return {"message": "Email sent successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/tasks", response_model=schemas.TaskOut)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    return crud.create_task(db, task)

@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return crud.get_tasks(db)

@app.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, upd: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = crud.update_task(db, task_id, upd)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Deleted successfully"}
