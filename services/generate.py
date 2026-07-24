"""Turns a candidate's resume + a target (role/company/research) into copy:
outreach emails, LinkedIn DMs, and cover letters. All grounded on the resume
so nothing is fabricated about the candidate."""
import json
import config
from services import llm

_RULES = (
    "Rules you must follow:\n"
    "- Only use facts about the candidate that appear in their resume. Never invent "
    "experience, numbers, or skills they don't have.\n"
    "- Be specific and concrete. Reference one real, relevant thing from the resume "
    "that connects to this company or role.\n"
    "- Sound like a real person, not a template. No clichés like 'I am writing to "
    "express my interest' or 'passionate about leveraging synergies'.\n"
    "- Match the company's actual work when research is provided; do not gush or flatter."
)


def _resume():
    r = config.resume_text()
    return r if r.strip() else "(No resume on file — write generically and flag that.)"


def outreach(company, role, contact_name="", research="", job_url=""):
    """Returns {'subject','email','linkedin_dm'} as parsed JSON from the model."""
    system = (
        "You write cold outreach for a university student seeking a software "
        "engineering co-op. You are warm, direct, and concise. " + _RULES
    )
    prompt = f"""Write cold outreach from this candidate to someone at a target company.

CANDIDATE RESUME:
{_resume()}

TARGET:
- Company: {company}
- Role / area of interest: {role or "software engineering co-op"}
- Contact name: {contact_name or "(unknown — use a role-appropriate greeting)"}
- Job link (if any): {job_url or "(none)"}

COMPANY RESEARCH (may be empty):
{research or "(none provided)"}

Produce THREE things:
1. A short email subject line (under 60 chars, specific, not salesy).
2. A cold email body: 90–150 words. Open with a real, specific hook tied to the
   company. State she's a Waterloo software engineering student seeking a co-op.
   Name ONE relevant project/experience from the resume. End with a low-friction
   ask (a quick call, or who to talk to). Sign as Anna Poutanen. Plain text only.
3. A LinkedIn DM version: under 300 characters, friendlier, no subject line.

Return ONLY valid JSON, no markdown fences:
{{"subject": "...", "email": "...", "linkedin_dm": "..."}}"""
    raw = llm.generate(system, prompt, max_tokens=900, temperature=0.7)
    return _parse_json(raw, fallback={"subject": "", "email": raw, "linkedin_dm": ""})


def cover_letter(job_description, company="", research=""):
    system = (
        "You write cover letters for a university student seeking a software "
        "engineering co-op. Professional, specific, no filler. " + _RULES
    )
    prompt = f"""Write a cover letter for this candidate for the role below.

CANDIDATE RESUME:
{_resume()}

COMPANY: {company or "(infer from the job description)"}

JOB DESCRIPTION:
{job_description}

COMPANY RESEARCH (may be empty):
{research or "(none provided)"}

Requirements:
- 3–4 short paragraphs, roughly 250–350 words total.
- Paragraph 1: why this company / role specifically (use the research and JD).
- Middle: map 2–3 concrete resume items to what the JD asks for. Use real detail.
- Close: brief, confident, with availability for a co-op term.
- Address it "Dear Hiring Team," unless a name is obvious in the JD.
- Return the letter as plain text only. No placeholders like [Your Name] — sign
  as Anna Poutanen. No markdown."""
    return llm.generate(system, prompt, max_tokens=1200, temperature=0.6)


def _parse_json(raw, fallback):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    try:
        start, end = raw.find("{"), raw.rfind("}")
        return json.loads(raw[start:end + 1])
    except Exception:
        return fallback
