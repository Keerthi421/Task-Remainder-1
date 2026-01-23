import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

def send_email(to_email: str, subject: str, body: str):
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_email or not smtp_password:
        raise ValueError(f"SMTP credentials missing. EMAIL: {bool(smtp_email)}, PASS: {bool(smtp_password)}")

    msg = EmailMessage()
    msg["From"] = smtp_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(smtp_email, smtp_password)
        smtp.send_message(msg)
