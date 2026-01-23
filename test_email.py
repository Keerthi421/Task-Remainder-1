import os
from dotenv import load_dotenv

load_dotenv()

print("SMTP_EMAIL =", os.getenv("SMTP_EMAIL"))
# Only print first/last 2 chars for security in logs, but print full length
raw_pass = os.getenv("SMTP_PASSWORD") or ""
mask_pass = raw_pass[:2] + "*" * (len(raw_pass) - 4) + raw_pass[-2:] if len(raw_pass) > 4 else "****"
print("SMTP_PASSWORD =", mask_pass)
print("PASS LENGTH =", len(raw_pass))

from app.email_utils import send_email

try:
    send_email(
        "sreekeerthig04@gmail.com",
        "Test Email ",
        "Bro SMTP is working"
    )
    print("Email sent!")
except Exception as e:
    print(f"FAILED: {e}")
