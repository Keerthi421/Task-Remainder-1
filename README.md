# Deadline Reminder Engine

A FastAPI-based backend system to generate task and medication reminders using deadline-aware scheduling logic with a rule-based scheduling algorithm that adapts reminder frequency by task difficulty.

## Features

- **CRUD APIs**: Create, read, update, and delete tasks
- **Rule-Based Scheduling Algorithm**: Reminder frequency adapts based on:
  - Task difficulty (easy/medium/hard)
  - Time remaining until deadline
  - Last 24 hours: hourly reminders
- **Automated Async Email Notifications**: Real email delivery via Gmail SMTP
- **Swagger Documentation**: Interactive API documentation with Pydantic validation
- **APScheduler Integration**: Background scheduler checks for reminders every minute

## Tech Stack

- **FastAPI**: Modern web framework
- **Python**: Backend logic
- **SQLAlchemy**: ORM for database
- **SQLite**: Database (easily upgradeable to PostgreSQL)
- **Pydantic**: Data validation
- **APScheduler**: Background task scheduling
- **SMTP**: Email delivery

## Project Structure

```
deadline-reminder-engine/
│── app/
│   │── __init__.py
│   │── main.py          # FastAPI app and endpoints
│   │── database.py      # Database configuration
│   │── models.py        # SQLAlchemy models
│   │── schemas.py       # Pydantic schemas
│   │── crud.py          # CRUD operations
│   │── scheduler.py     # Reminder scheduling logic
│   │── email_utils.py   # Email sending utility
│── requirements.txt     # Python dependencies
│── .env                 # Environment variables
│── README.md            # This file
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Task-Remainder-1
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Edit the `.env` file and add your Gmail credentials:

```env
SMTP_EMAIL=yourgmail@gmail.com
SMTP_PASSWORD=your_app_password
```

**Important**: You need a Gmail App Password (not your regular password):
1. Go to Google Account Settings
2. Security → 2-Step Verification
3. App Passwords → Generate new app password
4. Use the generated 16-character password in `.env`

### 4. Run the Application

```bash
uvicorn app.main:app --reload
```

The server will start at: `http://127.0.0.1:8000`

### 5. Access Swagger Documentation

Open your browser and visit:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## API Endpoints

### Create Task
```http
POST /tasks
Content-Type: application/json

{
  "title": "Complete Project Report",
  "description": "Finish the final project documentation",
  "due_date": "2026-01-25T18:00:00",
  "difficulty": "hard",
  "user_email": "user@example.com"
}
```

### List All Tasks
```http
GET /tasks
```

### Get Single Task
```http
GET /tasks/{task_id}
```

### Update Task
```http
PATCH /tasks/{task_id}
Content-Type: application/json

{
  "status": "completed"
}
```

### Delete Task
```http
DELETE /tasks/{task_id}
```

## Reminder Algorithm

The rule-based scheduling algorithm works as follows:

- **Easy tasks**: Remind every 24 hours
- **Medium tasks**: Remind every 12 hours
- **Hard tasks**: Remind every 6 hours
- **Last 24 hours before deadline**: Remind every hour (regardless of difficulty)

The scheduler runs in the background, checking every minute for tasks that need reminders.

## Database Schema

### Task Table

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| title | String | Task title |
| description | String | Task description |
| due_date | DateTime | Deadline |
| difficulty | String | easy/medium/hard |
| user_email | String | Recipient email |
| status | String | pending/completed |
| created_at | DateTime | Creation timestamp |
| last_reminded_at | DateTime | Last reminder sent |

## Future Enhancements

- [ ] PostgreSQL support for production
- [ ] JWT authentication for multi-user support
- [ ] Celery + Redis for scalable background jobs
- [ ] Frontend dashboard (React/Next.js)
- [ ] Deployment to Render/Railway
- [ ] SendGrid integration for better email delivery
- [ ] SMS notifications via Twilio

## License

MIT

