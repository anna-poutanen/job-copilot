"""Read a digest of recent mail across several accounts, read-only.

Uses IMAP with per-account credentials. This is the low-friction path and works
great for Gmail (use an App Password). Important caveat: Microsoft 365 / Outlook
(including most university email, e.g. Waterloo) has largely DISABLED basic-auth
IMAP — those accounts need OAuth2 (Microsoft Graph), which is a bigger setup.
See README. Nothing here deletes, sends, or modifies mail; it only reads headers
and a short snippet of recent messages.
"""
import imaplib
import email
from email.header import decode_header
import datetime as dt

import config


def _decode(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except LookupError:
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out).strip()


def _snippet(msg, limit=140) -> str:
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True) or b""
                    return " ".join(body.decode(errors="replace").split())[:limit]
        else:
            body = msg.get_payload(decode=True) or b""
            return " ".join(body.decode(errors="replace").split())[:limit]
    except Exception:
        pass
    return ""


def _read_account(acct: dict, since_days: int, per_account: int) -> dict:
    label = acct.get("label", acct.get("user", "account"))
    host = acct.get("imap_host", "")
    result = {"account": label, "messages": [], "error": ""}
    try:
        M = imaplib.IMAP4_SSL(host, acct.get("imap_port", 993))
        M.login(acct["user"], acct["password"])
        M.select("INBOX", readonly=True)  # readonly: never marks as read
        since = (dt.date.today() - dt.timedelta(days=since_days)).strftime("%d-%b-%Y")
        typ, data = M.search(None, f'(SINCE {since})')
        ids = data[0].split()[-per_account:] if data and data[0] else []
        for mid in reversed(ids):
            typ, msg_data = M.fetch(mid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            result["messages"].append({
                "from": _decode(msg.get("From")),
                "subject": _decode(msg.get("Subject")) or "(no subject)",
                "date": _decode(msg.get("Date")),
                "snippet": _snippet(msg),
            })
        M.logout()
    except Exception as e:
        result["error"] = str(e)
    return result


def digest(since_days: int = 2, per_account: int = 15) -> dict:
    accounts = config.email_accounts()
    if not accounts:
        return {"configured": False, "accounts": [],
                "note": "No email accounts configured — see data/accounts.json."}
    out = [_read_account(a, since_days, per_account) for a in accounts]
    total = sum(len(a["messages"]) for a in out)
    return {"configured": True, "since_days": since_days, "total": total, "accounts": out}
