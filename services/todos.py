"""Extract action items + deadlines from recent email into a to-do list.

Reads the (read-only) inbox digest, hands the subjects/snippets to the LLM, and
asks for discrete tasks with due dates resolved against today. Results are saved,
deduped by task text, so re-running doesn't pile up copies of the same task.
"""
import json
import datetime as dt
from zoneinfo import ZoneInfo

import config
from services import llm, email_inbox, storage


def _today_str() -> str:
    try:
        tz = ZoneInfo(config.TIMEZONE)
    except Exception:
        tz = ZoneInfo("America/Toronto")
    return dt.datetime.now(tz).strftime("%A, %Y-%m-%d")


def _parse_json_array(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    try:
        start, end = raw.find("["), raw.rfind("]")
        data = json.loads(raw[start:end + 1])
        return data if isinstance(data, list) else []
    except Exception:
        return []


def extract_from_inbox(since_days: int = 3) -> dict:
    inbox = email_inbox.digest(since_days=since_days)
    if not inbox.get("configured"):
        return {"error": "No email accounts configured — add them in data/accounts.json.",
                "added": 0, "todos": storage.list_todos()}

    lines = []
    for acct in inbox.get("accounts", []):
        for m in acct["messages"]:
            snip = f" — {m['snippet']}" if m.get("snippet") else ""
            lines.append(f"[{acct['account']}] From {m['from']} | \"{m['subject']}\"{snip}")
    if not lines:
        return {"error": "", "added": 0, "note": "No recent email to scan.",
                "todos": storage.list_todos()}

    system = (
        "You extract concrete to-do items from a person's recent email. Be strict: "
        "only include emails that actually require the person to DO something "
        "(reply, submit, register, pay, show up, prepare). Ignore newsletters, "
        "receipts, marketing, and pure FYIs. Never invent tasks."
    )
    prompt = f"""Today is {_today_str()}. Here are recent email subjects and snippets:

{chr(10).join(lines)}

Return ONLY a JSON array (no prose, no markdown fences). Each item:
{{"task": "<short imperative, e.g. 'Reply to recruiter at Faire'>",
  "due": "<YYYY-MM-DD if a date/deadline is stated or clearly implied, else ''>",
  "source": "<sender or subject it came from>",
  "priority": "<high|normal|low>"}}
Resolve relative dates ('by Friday', 'tomorrow') against today. If nothing
actionable, return []."""

    raw = llm.generate(system, prompt, max_tokens=900, temperature=0.2)
    items = _parse_json_array(raw)

    added = 0
    for it in items:
        task = (it.get("task") or "").strip()
        if not task:
            continue
        if storage.add_todo(task, due=(it.get("due") or "").strip(),
                            source=(it.get("source") or "").strip(),
                            priority=(it.get("priority") or "normal").strip()):
            added += 1

    return {"error": "", "added": added, "scanned": len(lines),
            "todos": storage.list_todos()}
