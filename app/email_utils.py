import requests
import json
import os
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

def send_email(to_email: str, subject: str, body: str):
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("SENDER_EMAIL") # Verify this in Brevo dashboard
    
    if not api_key or not sender_email:
        print("LOG: Missing Brevo API credentials. Skipping email.")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    
    payload = json.dumps({
        "sender": {
            "name": "Task Reminder App",
            "email": sender_email
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": subject,
        "textContent": body
    })
    
    headers = {
        'accept': 'application/json',
        'api-key': api_key,
        'content-type': 'application/json'
    }
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 201:
            print(f"LOG: Email sent successfully via Brevo to {to_email}")
        else:
            print(f"LOG: Failed to send email via Brevo. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"LOG: Exception sending email via Brevo: {e}")
