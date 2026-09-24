import csv
import io
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import (FastAPI, Depends, HTTPException, status,
                     UploadFile, File, Request)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .auth import (create_access_token, verify_password,
                   ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, jwt, JWTError)
from .database import Base, engine, get_db, run_migrations
from . import crud, schemas
from .scheduler import start_scheduler

load_dotenv()

Base.metadata.create_all(bind=engine)
run_migrations(engine)          # add new columns to existing DB without data loss

app = FastAPI(title="Deadline Reminder Engine")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

# ── Static pages ──────────────────────────────────────────────────────────────

@app.get("/")
def root():  return FileResponse("frontend/landing.html")

@app.get("/login")
def login(): return FileResponse("frontend/login.html")

@app.get("/app")
def app_page(): return FileResponse("frontend/index.html")

@app.get("/manifest.json")
def manifest(): return FileResponse("frontend/manifest.json")

@app.get("/sw.js")
def sw(): return FileResponse("frontend/sw.js", media_type="application/javascript")

# ── Auth helpers ──────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)],
                            db: Session = Depends(get_db)):
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Could not validate credentials",
                        headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise exc
    except JWTError:
        raise exc
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise exc
    return user

# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(400, "Email already registered")
    return crud.create_user(db, user)

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/count")
def count_users(db: Session = Depends(get_db)):
    return {"count": crud.get_user_count(db)}

@app.get("/users/me", response_model=schemas.UserOut)
def get_me(current_user: schemas.UserOut = Depends(get_current_user)):
    return current_user

# ── Profile ───────────────────────────────────────────────────────────────────

@app.get("/users/profile", response_model=schemas.ProfileOut)
def get_profile(db: Session = Depends(get_db),
                current_user: schemas.UserOut = Depends(get_current_user)):
    return crud.get_profile_out(db, current_user.email)

@app.patch("/users/profile", response_model=schemas.ProfileOut)
def update_profile(upd: schemas.ProfileUpdate, db: Session = Depends(get_db),
                   current_user: schemas.UserOut = Depends(get_current_user)):
    return crud.update_profile(db, current_user.email, upd)

# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/tasks/stats", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db),
              current_user: schemas.UserOut = Depends(get_current_user)):
    return crud.get_stats(db, current_user.email)

# ── AI endpoints ──────────────────────────────────────────────────────────────

@app.post("/tasks/parse")
def parse_nl(req: schemas.ParseRequest):
    from .ai_utils import parse_natural_language
    result = parse_natural_language(req.text)
    if result is None:
        raise HTTPException(503, "AI parsing unavailable – set ANTHROPIC_API_KEY in .env")
    return result

@app.post("/tasks/suggest-priority")
def suggest_priority(req: schemas.PriorityRequest):
    from .ai_utils import suggest_priority as _sp
    result = _sp(req.title, req.description)
    if result is None:
        raise HTTPException(503, "AI unavailable – set ANTHROPIC_API_KEY in .env")
    return {"priority": result}

# ── CSV import ────────────────────────────────────────────────────────────────

@app.post("/tasks/import", response_model=list[schemas.TaskOut])
async def import_tasks(file: UploadFile = File(...),
                       db: Session = Depends(get_db),
                       current_user: schemas.UserOut = Depends(get_current_user)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    content = (await file.read()).decode("utf-8-sig", errors="replace")
    reader  = csv.DictReader(io.StringIO(content))
    created = []
    errors  = []
    for i, row in enumerate(reader, start=2):
        try:
            task = schemas.TaskCreate(
                title       = row.get("title", "").strip() or "Untitled",
                description = row.get("description", "").strip(),
                due_date    = datetime.fromisoformat(row.get("due_date", "").strip()),
                priority    = row.get("priority", "low").strip().lower() or "low",
                tags        = row.get("tags", "").strip(),
            )
            created.append(crud.create_task(db, task, current_user.email))
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    if not created and errors:
        raise HTTPException(422, "; ".join(errors[:5]))
    return created

# ── Task CRUD ─────────────────────────────────────────────────────────────────

@app.post("/tasks", response_model=schemas.TaskOut)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db),
                current_user: schemas.UserOut = Depends(get_current_user)):
    return crud.create_task(db, task, current_user.email)

@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db),
               current_user: schemas.UserOut = Depends(get_current_user)):
    return crud.get_tasks(db, current_user.email)

@app.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db),
             current_user: schemas.UserOut = Depends(get_current_user)):
    t = crud.get_task(db, task_id, current_user.email)
    if not t:
        raise HTTPException(404, "Task not found")
    return t

@app.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, upd: schemas.TaskUpdate,
                db: Session = Depends(get_db),
                current_user: schemas.UserOut = Depends(get_current_user)):
    t = crud.update_task(db, task_id, upd, current_user.email)
    if not t:
        raise HTTPException(404, "Task not found")
    return t

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db),
                current_user: schemas.UserOut = Depends(get_current_user)):
    if not crud.delete_task(db, task_id, current_user.email):
        raise HTTPException(404, "Task not found")
    return {"message": "Deleted"}

# ── Public share ──────────────────────────────────────────────────────────────

@app.post("/tasks/{task_id}/share")
def share_task(task_id: int, db: Session = Depends(get_db),
               current_user: schemas.UserOut = Depends(get_current_user)):
    t = crud.generate_public_token(db, task_id, current_user.email)
    if not t:
        raise HTTPException(404, "Task not found")
    return {"public_url": f"/tasks/public/{t.public_token}",
            "token": t.public_token}

@app.get("/tasks/public/{token}")
def view_public_task(token: str, db: Session = Depends(get_db)):
    t = crud.get_task_by_public_token(db, token)
    if not t:
        raise HTTPException(404, "Link not found or expired")
    return {
        "title": t.title, "description": t.description,
        "due_date": t.due_date, "priority": t.priority,
        "status": t.status, "tags": t.tags,
    }

# ── Reorder ───────────────────────────────────────────────────────────────────

@app.post("/tasks/reorder")
def reorder_tasks(items: list[schemas.ReorderItem],
                  db: Session = Depends(get_db),
                  current_user: schemas.UserOut = Depends(get_current_user)):
    crud.reorder_tasks(db, items, current_user.email)
    return {"message": "Reordered"}

# ── Templates ─────────────────────────────────────────────────────────────────

@app.post("/templates", response_model=schemas.TemplateOut)
def create_template(tmpl: schemas.TemplateCreate, db: Session = Depends(get_db),
                    current_user: schemas.UserOut = Depends(get_current_user)):
    return crud.create_template(db, tmpl, current_user.email)

@app.get("/templates", response_model=list[schemas.TemplateOut])
def list_templates(db: Session = Depends(get_db),
                   current_user: schemas.UserOut = Depends(get_current_user)):
    return crud.get_templates(db, current_user.email)

@app.delete("/templates/{tmpl_id}")
def delete_template(tmpl_id: int, db: Session = Depends(get_db),
                    current_user: schemas.UserOut = Depends(get_current_user)):
    if not crud.delete_template(db, tmpl_id, current_user.email):
        raise HTTPException(404, "Template not found")
    return {"message": "Deleted"}

# ── Scheduler status ──────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    start_scheduler()

@app.get("/scheduler-status")
def scheduler_status():
    from .scheduler import scheduler
    return {"running": scheduler.running,
            "jobs": [str(j) for j in scheduler.get_jobs()]}
