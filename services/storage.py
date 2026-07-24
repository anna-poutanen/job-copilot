"""Tiny SQLite layer. Keeps found jobs, saved drafts, contacts, and an audit log of sends."""
import sqlite3
import json
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,            -- dedupe key (company|title|url)
    title TEXT, company TEXT, location TEXT, url TEXT,
    source TEXT, description TEXT, found_at REAL, status TEXT DEFAULT 'new'
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT,                 -- 'outreach_email' | 'linkedin_dm' | 'cover_letter'
    company TEXT, role TEXT, subject TEXT, body TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, email TEXT, company TEXT, role TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT, subject TEXT, dry_run INTEGER, status TEXT,
    detail TEXT, sent_at REAL
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.executescript(SCHEMA)


def save_jobs(jobs: list[dict]) -> int:
    """Insert jobs, ignoring duplicates. Returns count of newly added rows."""
    added = 0
    with _conn() as con:
        for j in jobs:
            key = f"{j.get('company','')}|{j.get('title','')}|{j.get('url','')}".lower()
            try:
                con.execute(
                    "INSERT INTO jobs (key,title,company,location,url,source,description,found_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (key, j.get("title"), j.get("company"), j.get("location"),
                     j.get("url"), j.get("source"), (j.get("description") or "")[:4000], time.time()),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass  # already have it
    return added


def list_jobs(limit=200) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM jobs ORDER BY found_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def set_job_status(job_id: int, status: str):
    with _conn() as con:
        con.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))


def save_draft(kind, company, role, subject, body) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO drafts (kind,company,role,subject,body,created_at) VALUES (?,?,?,?,?,?)",
            (kind, company, role, subject, body, time.time()),
        )
        return cur.lastrowid


def list_drafts(limit=100) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def log_send(recipient, subject, dry_run, status, detail=""):
    with _conn() as con:
        con.execute(
            "INSERT INTO send_log (recipient,subject,dry_run,status,detail,sent_at)"
            " VALUES (?,?,?,?,?,?)",
            (recipient, subject, 1 if dry_run else 0, status, detail, time.time()),
        )


def list_log(limit=100) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM send_log ORDER BY sent_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
