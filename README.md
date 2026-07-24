# Job Co-Pilot

A local app that helps you run a software co-op search: find postings, draft
cold outreach (email + LinkedIn DM), optionally auto-send the emails, and write
tailored cover letters from a pasted job description plus company research.

Everything runs on your own machine. Your resume, API key, and email password
never leave your computer.

---

## What it does

1. **Find jobs** — pulls early-career software postings from public, no-login job
   feeds and filters them to intern / co-op / new-grad software roles.
2. **Outreach** — generates a cold email *and* a LinkedIn DM grounded in your
   resume, with optional company research. You can edit, then preview or send.
3. **Cover letter** — paste a job description, get a tailored letter that maps
   your real resume items to what the posting asks for.
4. **Activity** — a local log of every preview and send.

## Setup (5 minutes)

```bash
cd job-copilot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env (see below)
python app.py
```

Open **http://127.0.0.1:5000**. The status chips at the top tell you what's
configured.

### The `.env` file
- `ANTHROPIC_API_KEY` — required for any writing. Get one at console.anthropic.com.
- `LLM_MODEL` — defaults to `claude-sonnet-5`; change if you prefer another model.
- `SMTP_*` — only needed to actually send email. For Gmail, enable 2FA and create
  an **App Password**, then use that as `SMTP_PASS`.
- `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` — optional extra job source (free).
- `GREENHOUSE_BOARDS` / `LEVER_BOARDS` — company job boards to scan. Add tokens
  for companies you're targeting (the token is the name in their careers URL,
  e.g. `boards.greenhouse.io/shopify` → `shopify`).

## Sending safely (read this once)

Sending is **preview-only by default**. Nothing is emailed until you tick
"Actually send" and confirm. Even then:
- sends are capped per run (`MAX_SENDS_PER_RUN`) and spaced out;
- every email carries your name, email, and a "reply STOP" opt-out line;
- everything is logged in the Activity tab.

Cold outreach to a hiring contact is normal, legitimate networking. Keep it
low-volume, personal, and honest. Canada's CASL and the US CAN-SPAM Act expect
real identification and an easy opt-out — both are built in — but the tool can't
judge tone for you, so read each message before it goes out.

## Honest limitations

- **No LinkedIn / Indeed scraping.** Both block automated access in their terms
  and break constantly. LinkedIn also has no API to send DMs, so the tool writes
  the DM text for you to paste in yourself.
- **Job feeds vary.** Public feeds (Remotive, Arbeitnow, Greenhouse, Lever) don't
  cover every company. The most reliable results come from adding target
  companies' Greenhouse/Lever tokens in `.env`.
- **Finding recipient emails is on you.** The tool doesn't harvest personal
  addresses. Use a contact you already have, or a company's public careers/jobs
  inbox.
- **Research is light-touch.** It reads Wikipedia and the company's own public
  site — enough to ground the writing, not a deep dossier.
- **Always review generated text.** It's grounded in your resume, but you're the
  one whose name is on it.

## Project layout

```
app.py                 Flask routes + validation
config.py              env / settings / status
services/
  llm.py               Anthropic wrapper
  jobs.py              public job-feed aggregation + filtering
  research.py          Wikipedia + website research
  generate.py          outreach + cover-letter prompts
  email_service.py     SMTP send with guardrails
  storage.py           SQLite (jobs, drafts, contacts, send log)
static/                index.html, style.css, app.js
data/resume.md         your resume (edit anytime)
```

Update your resume by editing `data/resume.md`. It's the source of truth for
everything the tool writes about you.
