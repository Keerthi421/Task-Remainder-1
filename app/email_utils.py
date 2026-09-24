import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Core send ──────────────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, body: str,
               html_body: str | None = None) -> bool:
    """Send via Brevo. Returns True only when Brevo accepted (201)."""
    api_key     = os.getenv("BREVO_API_KEY")
    sender_email= os.getenv("SENDER_EMAIL")

    if not api_key or not sender_email:
        print("LOG: Missing Brevo credentials – skipping email.")
        return False

    payload = {
        "sender": {"name": "Task Reminder", "email": sender_email},
        "to":     [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }
    if html_body:
        payload["htmlContent"] = html_body

    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"accept": "application/json", "api-key": api_key,
                     "content-type": "application/json"},
            data=json.dumps(payload),
            timeout=15
        )
        if resp.status_code == 201:
            print(f"LOG: Email sent to {to_email}")
            return True
        print(f"LOG: Brevo error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"LOG: Email exception: {e}")
    return False


# ── SMS (Twilio hook) ──────────────────────────────────────────────────────────

def send_sms(to_phone: str, message: str) -> bool:
    """Send SMS via Twilio. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE."""
    sid       = os.getenv("TWILIO_ACCOUNT_SID")
    token     = os.getenv("TWILIO_AUTH_TOKEN")
    from_num  = os.getenv("TWILIO_PHONE_NUMBER")
    if not all([sid, token, from_num]):
        return False
    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(body=message, from_=from_num, to=to_phone)
        return True
    except ImportError:
        print("LOG: twilio package not installed – install with: pip install twilio")
    except Exception as e:
        print(f"LOG: SMS error: {e}")
    return False


# ── Reminder email ─────────────────────────────────────────────────────────────

def send_reminder_email(task, task_time_str: str, now_str: str) -> bool:
    subject  = f"🔔 Reminder: {task.title}"
    priority_emoji = {"high": "🔴", "moderate": "🟡", "low": "🟢"}.get(task.priority, "⚪")

    # Sub-tasks checklist
    sub_items = ""
    try:
        subs = json.loads(task.sub_tasks or "[]")
        if subs:
            rows = "".join(
                f"<tr><td style='padding:4px 8px;'>{'✅' if s.get('done') else '☐'}</td>"
                f"<td style='padding:4px 8px;color:#{'aaa' if s.get('done') else '222'};'>"
                f"{'<s>' if s.get('done') else ''}{s['text']}{'</s>' if s.get('done') else ''}</td></tr>"
                for s in subs
            )
            sub_items = f"""
            <h4 style='margin:20px 0 8px;font-size:13px;color:#555;text-transform:uppercase;letter-spacing:1px;'>
              Checklist</h4>
            <table style='border-collapse:collapse;width:100%;'>{rows}</table>"""
    except Exception:
        pass

    html = f"""<!DOCTYPE html>
<html><body style='margin:0;padding:0;background:#f4f4f5;font-family:Inter,Arial,sans-serif;'>
<div style='max-width:560px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,.08);'>
  <div style='background:#080808;padding:32px 40px;'>
    <p style='margin:0;font-size:12px;font-weight:700;letter-spacing:2px;color:rgba(245,245,245,.5);
              text-transform:uppercase;'>Task Reminder</p>
    <h1 style='margin:12px 0 0;font-size:28px;font-weight:900;color:#f5f5f5;letter-spacing:-1px;'>
      {task.title}</h1>
  </div>
  <div style='padding:32px 40px;'>
    <table style='width:100%;border-collapse:collapse;margin-bottom:20px;'>
      <tr>
        <td style='padding:8px 0;font-size:12px;font-weight:600;letter-spacing:1px;
                   text-transform:uppercase;color:#999;width:120px;'>Priority</td>
        <td style='padding:8px 0;font-size:14px;color:#111;'>{priority_emoji} {task.priority.capitalize()}</td>
      </tr>
      <tr>
        <td style='padding:8px 0;font-size:12px;font-weight:600;letter-spacing:1px;
                   text-transform:uppercase;color:#999;'>Scheduled</td>
        <td style='padding:8px 0;font-size:14px;color:#111;'>{task_time_str}</td>
      </tr>
      {'<tr><td style="padding:8px 0;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#999;">Details</td><td style="padding:8px 0;font-size:14px;color:#111;">' + task.description + '</td></tr>' if task.description else ''}
    </table>
    {sub_items}
  </div>
  <div style='padding:20px 40px 32px;border-top:1px solid #f0f0f0;'>
    <p style='margin:0;font-size:12px;color:#bbb;'>Sent at {now_str} IST · Task Reminder App</p>
  </div>
</div>
</body></html>"""

    plain = f"Reminder: {task.title}\nPriority: {task.priority}\nScheduled: {task_time_str}"
    return send_email(task.user_email, subject, plain, html)


# ── Weekly digest ──────────────────────────────────────────────────────────────

def send_weekly_digest(to_email: str, completed: list, upcoming: list):
    def _row(t, show_status=True):
        priority_emoji = {"high": "🔴", "moderate": "🟡", "low": "🟢"}.get(t.priority, "⚪")
        due = t.due_date.strftime("%b %d, %I:%M %p") if t.due_date else ""
        status_badge = ""
        if show_status:
            status_badge = "<span style='background:#e8fef0;color:#16a34a;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:700;margin-left:8px;'>✓</span>"
        return f"""<tr style='border-bottom:1px solid #f4f4f5;'>
          <td style='padding:10px 0;font-size:14px;color:#111;'>{priority_emoji} {t.title}{status_badge}</td>
          <td style='padding:10px 0;font-size:13px;color:#888;text-align:right;'>{due}</td></tr>"""

    completed_rows = "".join(_row(t) for t in completed[:10]) if completed else \
        "<tr><td colspan='2' style='padding:16px 0;color:#bbb;font-size:14px;'>No tasks completed last week.</td></tr>"
    upcoming_rows  = "".join(_row(t, False) for t in upcoming[:10]) if upcoming else \
        "<tr><td colspan='2' style='padding:16px 0;color:#bbb;font-size:14px;'>No tasks due this week.</td></tr>"

    html = f"""<!DOCTYPE html>
<html><body style='margin:0;padding:0;background:#f4f4f5;font-family:Inter,Arial,sans-serif;'>
<div style='max-width:580px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,.08);'>
  <div style='background:#080808;padding:32px 40px;'>
    <p style='margin:0;font-size:12px;font-weight:700;letter-spacing:2px;color:rgba(245,245,245,.4);
              text-transform:uppercase;'>Weekly Digest</p>
    <h1 style='margin:8px 0 0;font-size:26px;font-weight:900;color:#f5f5f5;letter-spacing:-1px;'>
      Your Week in Review.</h1>
  </div>
  <div style='padding:32px 40px;'>
    <h3 style='margin:0 0 12px;font-size:13px;font-weight:700;letter-spacing:1.2px;
               text-transform:uppercase;color:#555;'>✅ Completed ({len(completed)})</h3>
    <table style='width:100%;border-collapse:collapse;'>{completed_rows}</table>

    <h3 style='margin:28px 0 12px;font-size:13px;font-weight:700;letter-spacing:1.2px;
               text-transform:uppercase;color:#555;'>📅 Due This Week ({len(upcoming)})</h3>
    <table style='width:100%;border-collapse:collapse;'>{upcoming_rows}</table>
  </div>
  <div style='padding:20px 40px 28px;border-top:1px solid #f0f0f0;'>
    <p style='margin:0;font-size:12px;color:#bbb;'>To unsubscribe from weekly digests,
      update your profile settings in the app.</p>
  </div>
</div>
</body></html>"""

    plain = (f"Weekly Digest\n\nCompleted: {len(completed)}\nUpcoming: {len(upcoming)}\n\n"
             + "\n".join(f"✓ {t.title}" for t in completed[:10])
             + "\n\nDue this week:\n"
             + "\n".join(f"• {t.title}" for t in upcoming[:10]))
    send_email(to_email, "📅 Your Weekly Task Digest", plain, html)
