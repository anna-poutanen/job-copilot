"""Tiny SQLite layer. Keeps found jobs, saved drafts, contacts, and an audit log of sends."""
import sqlite3
import json
import time
from contextlib import contextmanager

import config

PIPELINE_STAGES = ["saved", "applied", "interviewing", "offer", "rejected"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,            -- dedupe key (company|title|url)
    title TEXT, company TEXT, location TEXT, url TEXT,
    source TEXT, description TEXT, found_at REAL, status TEXT DEFAULT 'new',
    notes TEXT DEFAULT '', updated_at REAL
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
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,           -- dedupe key so re-extraction doesn't duplicate
    task TEXT, due TEXT, source TEXT, priority TEXT DEFAULT 'normal',
    done INTEGER DEFAULT 0, created_at REAL
);
"""


def _migrate(con):
    """Add columns introduced after the first release, if an old DB exists."""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(jobs)").fetchall()}
    if "notes" not in cols:
        con.execute("ALTER TABLE jobs ADD COLUMN notes TEXT DEFAULT ''")
    if "updated_at" not in cols:
        con.execute("ALTER TABLE jobs ADD COLUMN updated_at REAL")


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
        _migrate(con)


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
        con.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?",
                    (status, time.time(), job_id))


def update_job(job_id: int, status=None, notes=None):
    """Update a job's pipeline stage and/or notes."""
    sets, vals = [], []
    if status is not None:
        sets.append("status=?"); vals.append(status)
    if notes is not None:
        sets.append("notes=?"); vals.append(notes)
    if not sets:
        return
    sets.append("updated_at=?"); vals.append(time.time())
    vals.append(job_id)
    with _conn() as con:
        con.execute(f"UPDATE jobs SET {','.join(sets)} WHERE id=?", vals)


def add_application(company, role, url="", notes="") -> int:
    """Manually add an application (e.g. one found off-platform), straight into 'saved'."""
    now = time.time()
    key = f"manual|{company}|{role}|{url}|{now}".lower()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO jobs (key,title,company,location,url,source,description,"
            "found_at,status,notes,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (key, role, company, "", url, "manual", "", now, "saved", notes, now),
        )
        return cur.lastrowid


def delete_job(job_id: int):
    with _conn() as con:
        con.execute("DELETE FROM jobs WHERE id=?", (job_id,))


def pipeline_jobs() -> list[dict]:
    """Only jobs the user is actively tracking (anything past the 'new' bucket)."""
    marks = ",".join("?" * len(PIPELINE_STAGES))
    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM jobs WHERE status IN ({marks}) "
            "ORDER BY COALESCE(updated_at, found_at) DESC", PIPELINE_STAGES
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- to-do list ----------
def add_todo(task, due="", source="", priority="normal") -> bool:
    """Insert a todo, deduped by normalized task text. Returns True if newly added."""
    key = " ".join((task or "").lower().split())[:200]
    if not key:
        return False
    with _conn() as con:
        try:
            con.execute(
                "INSERT INTO todos (key,task,due,source,priority,done,created_at)"
                " VALUES (?,?,?,?,?,0,?)",
                (key, task.strip(), due or "", source or "", priority or "normal", time.time()),
            )
            return True
        except sqlite3.IntegrityError:
            return False  # already have this task


def list_todos(include_done=True) -> list[dict]:
    q = "SELECT * FROM todos"
    if not include_done:
        q += " WHERE done=0"
    # open first, then by due date (blank dues last), then newest
    q += " ORDER BY done ASC, CASE WHEN due='' THEN 1 ELSE 0 END, due ASC, created_at DESC"
    with _conn() as con:
        return [dict(r) for r in con.execute(q).fetchall()]


def set_todo_done(todo_id: int, done: bool):
    with _conn() as con:
        con.execute("UPDATE todos SET done=? WHERE id=?", (1 if done else 0, todo_id))


def delete_todo(todo_id: int):
    with _conn() as con:
        con.execute("DELETE FROM todos WHERE id=?", (todo_id,))


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
