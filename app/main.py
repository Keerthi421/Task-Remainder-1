from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
from datetime import timedelta
from .auth import create_access_token, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, jwt, JWTError
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
    return FileResponse("frontend/landing.html")

@app.get("/login")
def read_login():
    return FileResponse("frontend/login.html")

@app.get("/app")
def read_app():
    return FileResponse("frontend/index.html")

# Auth & User Endpoints

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/count")
def count_users(db: Session = Depends(get_db)):
    return {"count": crud.get_user_count(db)}

# Task Endpoints (Protected)

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
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db), current_user: schemas.UserOut = Depends(get_current_user)):
    # Override user_email with logged in user's email for security
    task.user_email = current_user.email
    return crud.create_task(db, task)

@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db), current_user: schemas.UserOut = Depends(get_current_user)):
    # In a real app we might filter by current_user.email here
    # return crud.get_tasks_by_user(db, current_user.email)
    return crud.get_tasks(db)

@app.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db), current_user: schemas.UserOut = Depends(get_current_user)):
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, upd: schemas.TaskUpdate, db: Session = Depends(get_db), current_user: schemas.UserOut = Depends(get_current_user)):
    task = crud.update_task(db, task_id, upd)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: schemas.UserOut = Depends(get_current_user)):
    ok = crud.delete_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Deleted successfully"}
