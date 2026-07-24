"""Central configuration. All secrets come from environment / .env — never hardcoded."""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- LLM (Anthropic) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5").strip()

# --- Email sending (SMTP) ---
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _int("SMTP_PORT", 465)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
FROM_NAME = os.getenv("FROM_NAME", "Anna Poutanen").strip()
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER).strip()

# --- Safety guardrails for autosend ---
MAX_SENDS_PER_RUN = _int("MAX_SENDS_PER_RUN", 20)   # hard cap per send request
SEND_DELAY_SECONDS = _int("SEND_DELAY_SECONDS", 4)  # spacing between messages

# --- Optional job-board API (Adzuna) ---
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()

# --- Daily agenda / inbox ---
TIMEZONE = os.getenv("TIMEZONE", "America/Toronto").strip()

# --- Files ---
RESUME_PATH = DATA_DIR / "resume.md"
DB_PATH = DATA_DIR / "app.db"
ACCOUNTS_PATH = DATA_DIR / "accounts.json"  # calendar feeds + email accounts (gitignored)

# Greenhouse / Lever board tokens to pull co-op/intern postings from.
# These are public job-board JSON feeds (no scraping, no login). Edit freely.
GREENHOUSE_BOARDS = [
    b.strip() for b in os.getenv(
        "GREENHOUSE_BOARDS",
        "shopify,stripe,figma,databricks,affirm,samsara,wealthsimple,faire"
    ).split(",") if b.strip()
]
LEVER_BOARDS = [
    b.strip() for b in os.getenv(
        "LEVER_BOARDS",
        "cohere,ada,plotly,benchsci"
    ).split(",") if b.strip()
]


def resume_text() -> str:
    if RESUME_PATH.exists():
        return RESUME_PATH.read_text(encoding="utf-8")
    return ""


def _accounts_file() -> dict:
    if ACCOUNTS_PATH.exists():
        try:
            return json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print("accounts.json parse error:", e)
    return {}


def calendar_feeds() -> list[dict]:
    """[{label, url}, ...] — ICS feed URLs to merge into the daily agenda."""
    return _accounts_file().get("calendars", [])


def email_accounts() -> list[dict]:
    """[{label, imap_host, imap_port, user, password}, ...] — read-only inbox digest."""
    return _accounts_file().get("email_accounts", [])


def status() -> dict:
    """What is configured right now — surfaced in the UI so nothing fails silently."""
    return {
        "llm_ready": bool(ANTHROPIC_API_KEY),
        "model": LLM_MODEL,
        "smtp_ready": bool(SMTP_HOST and SMTP_USER and SMTP_PASS),
        "from_email": FROM_EMAIL,
        "adzuna_ready": bool(ADZUNA_APP_ID and ADZUNA_APP_KEY),
        "resume_loaded": RESUME_PATH.exists() and bool(resume_text().strip()),
        "max_sends_per_run": MAX_SENDS_PER_RUN,
        "calendars": len(calendar_feeds()),
        "email_accounts": len(email_accounts()),
        "timezone": TIMEZONE,
    }
