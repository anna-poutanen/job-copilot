"""Job Co-Pilot — a local Flask app for a software co-op search.

Run:  python app.py   ->  http://127.0.0.1:5000
All heavy lifting lives in services/. This file is only routing + validation.
"""
from flask import Flask, request, jsonify, send_from_directory

import config
from services import storage, jobs, research, generate, email_service, llm

app = Flask(__name__, static_folder="static", static_url_path="")
storage.init_db()


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/config")
def get_config():
    return jsonify(config.status())


# ---------- resume ----------
@app.get("/api/resume")
def get_resume():
    return jsonify({"resume": config.resume_text()})


@app.post("/api/resume")
def set_resume():
    text = (request.json or {}).get("resume", "")
    config.RESUME_PATH.write_text(text, encoding="utf-8")
    return jsonify({"ok": True, "chars": len(text)})


# ---------- jobs ----------
@app.post("/api/jobs/search")
def jobs_search():
    d = request.json or {}
    res = jobs.search(
        query=d.get("query", ""),
        location=d.get("location", ""),
        sources=d.get("sources"),
        limit=int(d.get("limit", 60)),
    )
    res["added"] = storage.save_jobs(res["jobs"])
    return jsonify(res)


@app.get("/api/jobs")
def jobs_list():
    return jsonify({"jobs": storage.list_jobs()})


@app.post("/api/jobs/status")
def jobs_status():
    d = request.json or {}
    storage.set_job_status(int(d["id"]), d.get("status", "new"))
    return jsonify({"ok": True})


# ---------- research ----------
@app.post("/api/research")
def do_research():
    d = request.json or {}
    text = research.research_company(d.get("company", ""), d.get("url", ""))
    return jsonify({"research": text})


# ---------- generation ----------
@app.post("/api/generate/outreach")
def gen_outreach():
    d = request.json or {}
    try:
        research_text = d.get("research", "")
        if d.get("do_research") and not research_text:
            research_text = research.research_company(d.get("company", ""), d.get("company_url", ""))
        out = generate.outreach(
            company=d.get("company", ""), role=d.get("role", ""),
            contact_name=d.get("contact_name", ""), research=research_text,
            job_url=d.get("job_url", ""),
        )
        if out.get("subject"):
            storage.save_draft("outreach_email", d.get("company", ""), d.get("role", ""),
                               out.get("subject", ""), out.get("email", ""))
        out["research_used"] = research_text
        return jsonify(out)
    except llm.LLMNotConfigured as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/generate/cover-letter")
def gen_cover():
    d = request.json or {}
    jd = (d.get("job_description") or "").strip()
    if len(jd) < 40:
        return jsonify({"error": "Paste the full job description (a bit more text needed)."}), 400
    try:
        research_text = ""
        if d.get("do_research"):
            research_text = research.research_company(d.get("company", ""), d.get("company_url", ""))
        letter = generate.cover_letter(jd, company=d.get("company", ""), research=research_text)
        storage.save_draft("cover_letter", d.get("company", ""), "", "", letter)
        return jsonify({"cover_letter": letter, "research_used": research_text})
    except llm.LLMNotConfigured as e:
        return jsonify({"error": str(e)}), 400


# ---------- email sending ----------
@app.post("/api/email/send")
def email_send():
    d = request.json or {}
    messages = d.get("messages", [])
    dry_run = bool(d.get("dry_run", True))  # default safe
    if not messages:
        return jsonify({"error": "No messages to send."}), 400
    try:
        result = email_service.send_batch(messages, dry_run=dry_run)
        return jsonify(result)
    except email_service.EmailNotConfigured as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/log")
def get_log():
    return jsonify({"log": storage.list_log()})


if __name__ == "__main__":
    print("\n  Job Co-Pilot running at  http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
