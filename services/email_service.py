"""Sends email over SMTP with deliberate guardrails:
  - Dry-run is the DEFAULT. A real send only happens when dry_run is explicitly False.
  - A per-request cap (MAX_SENDS_PER_RUN) can never be exceeded.
  - Recipient addresses are validated; each send is spaced out and logged.
  - A plain-text identifying signature is appended so recipients know who you are.

Cold outreach is legitimate networking, but it is your responsibility to keep it
honest and low-volume. Canada's CASL and the US CAN-SPAM Act expect real
identification and an easy way to opt out — both are built in below.
"""
import re
import ssl
import time
import smtplib
from email.message import EmailMessage

import config
from services import storage

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailNotConfigured(RuntimeError):
    pass


def _valid(addr: str) -> bool:
    return bool(EMAIL_RE.match((addr or "").strip()))


def _with_signature(body: str) -> str:
    sig = (
        f"\n\n—\n{config.FROM_NAME}\n{config.FROM_EMAIL}\n"
        "University of Waterloo, Software Engineering\n"
        "Reply STOP and I won't contact you again."
    )
    return body.rstrip() + sig


def _smtp_ready():
    if not (config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASS):
        raise EmailNotConfigured(
            "SMTP is not configured. Add SMTP_HOST, SMTP_USER and SMTP_PASS to .env "
            "(for Gmail, create an App Password)."
        )


def _send_one(to_addr, subject, body):
    msg = EmailMessage()
    msg["From"] = f"{config.FROM_NAME} <{config.FROM_EMAIL}>"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(_with_signature(body))
    ctx = ssl.create_default_context()
    if config.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx) as s:
            s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)
    else:  # 587 / STARTTLS
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
            s.starttls(context=ctx)
            s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)


def send_batch(messages: list[dict], dry_run: bool = True) -> dict:
    """messages: [{to, subject, body}, ...].
    dry_run=True  -> validate + log only, send nothing (safe default).
    dry_run=False -> actually send, capped at MAX_SENDS_PER_RUN, spaced out."""
    if not dry_run:
        _smtp_ready()

    if len(messages) > config.MAX_SENDS_PER_RUN:
        messages = messages[: config.MAX_SENDS_PER_RUN]
        capped = True
    else:
        capped = False

    results = []
    for i, m in enumerate(messages):
        to = (m.get("to") or "").strip()
        subject = (m.get("subject") or "").strip()
        body = m.get("body") or ""
        if not _valid(to):
            storage.log_send(to, subject, dry_run, "invalid", "bad email address")
            results.append({"to": to, "status": "invalid"})
            continue
        if dry_run:
            storage.log_send(to, subject, True, "preview", "dry-run, not sent")
            results.append({"to": to, "status": "preview"})
            continue
        try:
            _send_one(to, subject, body)
            storage.log_send(to, subject, False, "sent", "")
            results.append({"to": to, "status": "sent"})
        except Exception as e:
            storage.log_send(to, subject, False, "error", str(e))
            results.append({"to": to, "status": "error", "detail": str(e)})
        if not dry_run and i < len(messages) - 1:
            time.sleep(config.SEND_DELAY_SECONDS)

    sent = sum(1 for r in results if r["status"] == "sent")
    return {
        "dry_run": dry_run, "capped": capped, "processed": len(results),
        "sent": sent, "results": results,
    }
