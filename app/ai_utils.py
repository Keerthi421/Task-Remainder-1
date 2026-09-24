"""Claude API helpers — degrade gracefully when ANTHROPIC_API_KEY is not set."""
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic package not installed – AI features disabled")
        return None


def parse_natural_language(text: str) -> dict | None:
    """
    Parse a free-text task description into structured fields.
    Returns dict with keys: title, description, due_date, priority, tags
    or None if AI is unavailable.
    """
    client = _client()
    if not client:
        return None

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt = f"""Parse this task into structured JSON. Current date/time: {now}

Task: "{text}"

Return ONLY valid JSON (no markdown):
{{
  "title": "concise task title (max 10 words)",
  "description": "details, or empty string",
  "due_date": "YYYY-MM-DDTHH:MM or null if not mentioned",
  "priority": "low|moderate|high",
  "tags": "comma-separated tags or empty string"
}}"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = msg.content[0].text.strip()
        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        logger.error(f"parse_natural_language failed: {e}")
        return None


def suggest_priority(title: str, description: str = "") -> str | None:
    """
    Suggest priority (low|moderate|high) for a task.
    Returns None if AI is unavailable.
    """
    client = _client()
    if not client:
        return None

    prompt = f"""Suggest the urgency/priority of this task.
Title: "{title}"
Description: "{description}"

Reply with exactly one word: low, moderate, or high"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        result = msg.content[0].text.strip().lower().split()[0]
        return result if result in ("low", "moderate", "high") else None
    except Exception as e:
        logger.error(f"suggest_priority failed: {e}")
        return None
