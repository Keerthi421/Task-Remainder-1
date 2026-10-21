import hmac as _hmac
import hashlib
import json
import os
from html import escape
import requests
from dotenv import load_dotenv

load_dotenv()


# ── Snooze token ───────────────────────────────────────────────────────────────

def make_snooze_token(task_id: int, user_email: str) -> str:
    """HMAC-signed token that authorises a one-click snooze from an email link."""
    secret = os.getenv("SECRET_KEY", "")
    msg = f"snooze:{task_id}:{user_email}"
    return _hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


# ── Slack webhook ──────────────────────────────────────────────────────────────

def send_slack_webhook(webhook_url: str, message: str) -> bool:
    """POST a plain-text message to a Slack incoming webhook URL."""
    if not webhook_url:
        return False
    try:
        resp = requests.post(webhook_url, json={"text": message}, timeout=10)
        if resp.status_code == 200:
            print(f"LOG: Slack webhook sent")
            return True
        print(f"LOG: Slack webhook error {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"LOG: Slack webhook exception: {e}")
    return False

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


# ── SMS / WhatsApp (Twilio) ────────────────────────────────────────────────────

def _twilio_client():
    """Return (client, from_sms, from_wa) or None if not configured."""
    try:
        from twilio.rest import Client
    except ImportError:
        print("LOG: twilio not installed – run: pip install twilio")
        return None, None, None
    sid      = os.getenv("TWILIO_ACCOUNT_SID")
    token    = os.getenv("TWILIO_AUTH_TOKEN")
    from_sms = os.getenv("TWILIO_PHONE_NUMBER")      # e.g. +12345678900
    from_wa  = os.getenv("TWILIO_WHATSAPP_NUMBER",   # e.g. +14155238886 (Twilio sandbox)
                         "whatsapp:+14155238886")
    if not all([sid, token, from_sms]):
        return None, None, None
    return Client(sid, token), from_sms, from_wa


def send_sms(to_phone: str, message: str) -> bool:
    """Send SMS via Twilio. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER."""
    client, from_sms, _ = _twilio_client()
    if not client:
        return False
    try:
        client.messages.create(body=message, from_=from_sms, to=to_phone)
        print(f"LOG: SMS sent to {to_phone}")
        return True
    except Exception as e:
        print(f"LOG: SMS error: {e}")
    return False


def send_whatsapp(to_phone: str, message: str) -> bool:
    """Send a WhatsApp message via Twilio.
    `to_phone` must be in E.164 format (e.g. +919876543210).
    Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER.
    Optionally set TWILIO_WHATSAPP_NUMBER (defaults to Twilio sandbox +14155238886).
    """
    client, _, from_wa = _twilio_client()
    if not client:
        return False
    try:
        wa_to = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone
        wa_from = from_wa if from_wa.startswith("whatsapp:") else f"whatsapp:{from_wa}"
        client.messages.create(body=message, from_=wa_from, to=wa_to)
        print(f"LOG: WhatsApp sent to {to_phone}")
        return True
    except Exception as e:
        print(f"LOG: WhatsApp error: {e}")
    return False


# ── Reminder email ─────────────────────────────────────────────────────────────

def _snooze_buttons_html(task_id: int, base_url: str | None, token: str | None) -> str:
    if not base_url or not token:
        return ""
    btn_style = ("display:inline-block;background:#f5f5f5;color:#080808;"
                 "text-decoration:none;font-size:12px;font-weight:700;"
                 "letter-spacing:.8px;text-transform:uppercase;"
                 "padding:10px 20px;border-radius:8px;margin-right:8px;")
    url1h  = f"{base_url}/tasks/{task_id}/snooze?hours=1&token={token}"
    url1d  = f"{base_url}/tasks/{task_id}/snooze?hours=24&token={token}"
    return (f"<p style='margin:0 0 12px;font-size:12px;color:#888;'>Not ready yet? Snooze it:</p>"
            f"<a href='{url1h}' style='{btn_style}'>⏱ Snooze 1 hour</a>"
            f"<a href='{url1d}' style='{btn_style}'>⏰ Snooze 1 day</a>"
            f"<br style='margin-bottom:16px;'>")


def send_reminder_email(task, task_time_str: str, now_str: str,
                        override_email: str | None = None,
                        snooze_base_url: str | None = None,
                        snooze_token: str | None = None) -> bool:
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
      {'<tr><td style="padding:8px 0;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#999;">Repeats</td><td style="padding:8px 0;font-size:14px;color:#111;">' + escape(task.recurrence_summary) + '</td></tr>' if getattr(task, 'recurrence_summary', None) else ''}
    </table>
    {sub_items}
  </div>
  <div style='padding:20px 40px 32px;border-top:1px solid #f0f0f0;'>
    {_snooze_buttons_html(task.id, snooze_base_url, snooze_token)}
    <p style='margin:0;font-size:12px;color:#bbb;'>Sent at {now_str} · Task Reminder App</p>
  </div>
</div>
</body></html>"""

    plain = f"Reminder: {task.title}\nPriority: {task.priority}\nScheduled: {task_time_str}"
    to = override_email or task.user_email
    return send_email(to, subject, plain, html)


# ── Password reset email ───────────────────────────────────────────────────────

def send_reset_email(to_email: str, reset_link: str) -> bool:
    subject = "🔑 Reset your Task Reminder password"
    html = f"""<!DOCTYPE html>
<html><body style='margin:0;padding:0;background:#f4f4f5;font-family:Inter,Arial,sans-serif;'>
<div style='max-width:520px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,.08);'>
  <div style='background:#080808;padding:32px 40px;'>
    <p style='margin:0;font-size:12px;font-weight:700;letter-spacing:2px;color:rgba(245,245,245,.5);
              text-transform:uppercase;'>Task Reminder</p>
    <h1 style='margin:12px 0 0;font-size:26px;font-weight:900;color:#f5f5f5;letter-spacing:-1px;'>
      Reset your password.</h1>
  </div>
  <div style='padding:32px 40px;'>
    <p style='font-size:15px;color:#444;line-height:1.6;margin:0 0 24px;'>
      We received a request to reset the password for <strong>{escape(to_email)}</strong>.
      Click the button below to choose a new password. This link expires in <strong>1 hour</strong>.</p>
    <a href='{reset_link}' style='display:inline-block;background:#080808;color:#f5f5f5;
       text-decoration:none;font-size:13px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;
       padding:14px 32px;border-radius:8px;'>Reset Password →</a>
    <p style='margin:24px 0 0;font-size:12px;color:#bbb;'>
      If you didn't request this, you can safely ignore this email. Your password won't change.</p>
  </div>
</div>
</body></html>"""
    plain = f"Reset your Task Reminder password\n\nClick this link (expires in 1 hour):\n{reset_link}\n\nIf you didn't request this, ignore this email."
    return send_email(to_email, subject, plain, html)


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
