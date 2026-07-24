# Job Co-Pilot

*A command center I built to run my life and my co-op search from one place

Between varsity nordic skiing, the Concrete Canoe and Electrium Mobility design
teams, the clubs I'm in, tutoring, coaching, and reffing on the side, and hunting
for co-op terms, I kept losing track of where I needed to be and which
applications I'd actually sent. So I built the tool I wished existed: one screen
that pulls my calendars and inboxes together, turns my email into a to-do list,
finds co-op postings, tracks my applications, and drafts the outreach and cover
letters I'd otherwise be writing one at a time at 1am.

At my last co-op I built an AI prospecting tool — firm research, contact
sourcing, personalized outreach, automated sending. This is me pointing that
same idea at my own job search.

Everything runs locally on my own machine. My resume, API key, and email
passwords never leave my computer.

---

## What it does

0. **Today** — all my calendars merged into one agenda (ski practice, canoe
   meetings, classes, shifts), plus a digest of recent email across accounts,
   and a one-click "morning brief" that reads the day back to me.
1. **To-dos** — scans recent email and pulls out anything that needs an action
   (replies, deadlines, registrations) into a checklist, with due dates resolved
   against today. I can add my own tasks too and check them off.
2. **Find jobs** — pulls early-career software postings from public, no-login job
   feeds and filters them down to intern / co-op / new-grad software roles.
3. **Pipeline** — my application tracker: Saved → Applied → Interviewing → Offer →
   Rejected. I track jobs straight from the Find tab, or add ones I found elsewhere.
4. **Outreach** — drafts a cold email *and* a LinkedIn DM grounded in my resume,
   with optional company research. I edit, then preview or send.
5. **Cover letter** — I paste a job description and get a tailored letter that maps
   my real resume items to what the posting is asking for.
6. **Activity** — a local log of every preview and send, so I can see what went out.

## Setup (about 5 minutes)

```bash
cd job-copilot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then fill in the keys below
python app.py
```

Open **http://127.0.0.1:5000**. The status chips along the top tell me what's
configured and what still needs a key.

### The `.env` file
- `ANTHROPIC_API_KEY` — needed for any writing. From console.anthropic.com.
- `LLM_MODEL` — defaults to `claude-sonnet-5`; swap if I want a different model.
- `TIMEZONE` — `America/Toronto` for me, so the agenda lines up with Waterloo time.
- `SMTP_*` — only needed to actually send email (Gmail App Password goes in `SMTP_PASS`).
- `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` — optional extra job source (free key).
- `GREENHOUSE_BOARDS` / `LEVER_BOARDS` — company boards to scan. I add tokens for
  places I'm targeting — the token is the name in their careers URL, e.g.
  `boards.greenhouse.io/shopify` → `shopify`. Seeded with some Canadian and
  co-op-friendly companies (Shopify, Wealthsimple, Cohere, Faire, …).

## Wiring up Today (my calendars + email)

Copy `data/accounts.example.json` to `data/accounts.json` and fill it in — it's
gitignored, so my passwords stay on my machine.

**Calendars** use ICS feed URLs (read-only, no OAuth, work everywhere):
- Google Calendar → Settings → the calendar → "Secret address in iCal format".
- Outlook → Settings → Calendar → Shared calendars → Publish → the `.ics` link.
- My class/training schedule usually has an "export to iCal" option too.

Recurring stuff like Tuesday ski practice and weekly canoe meetings expands
correctly and shows in my timezone.

**Email** uses read-only IMAP (never sends, deletes, or even marks mail as read):
- **Gmail works** — turn on 2FA, create an App Password, use it as `password`.
- **My Waterloo email needs more work.** Waterloo runs on Microsoft 365, and
  Microsoft has largely **disabled basic-auth IMAP**, so a plain password won't
  log in. That account needs OAuth2 (Microsoft Graph) — a bigger setup I haven't
  added yet. My Outlook *calendar* still works through ICS publishing; it's only
  inbox reading that's blocked.

## Sending email safely

Sending is **preview-only by default** — nothing actually goes out until I tick
"Actually send" and confirm. Even then, sends are capped per run and spaced out,
every message carries my name, email, and a "reply STOP" opt-out line, and it all
lands in the Activity log.

Cold outreach to a hiring contact is normal networking, but I keep it low-volume,
personal, and honest. Canada's CASL and the US CAN-SPAM Act expect real
identification and an easy opt-out (both built in) — but the tool can't judge tone
for me, so I read every message before it goes out.

## Things I deliberately left out (and why)

- **No LinkedIn / Indeed scraping.** Both block automated access in their terms
  and break constantly. LinkedIn also has no API for sending DMs — so the tool
  writes the DM text and I paste it in myself.
- **Job feeds don't cover everything.** Public feeds (Remotive, Arbeitnow,
  Greenhouse, Lever) miss plenty of companies. Best results come from adding my
  target companies' board tokens in `.env`.
- **Finding recipient emails is on me.** The tool doesn't harvest personal
  addresses — I use a contact I already have or a public careers inbox.
- **Research is light-touch.** It reads Wikipedia and the company's own site —
  enough to ground the writing, not a full dossier.
- **I always read the output.** It's grounded in my resume, but my name's on it.

## Project layout

```
app.py                 Flask routes + validation
config.py              env / settings / status
services/
  llm.py               Anthropic wrapper
  jobs.py              public job-feed aggregation + filtering
  research.py          Wikipedia + website research
  generate.py          outreach + cover-letter prompts
  email_service.py     SMTP send with guardrails (outbound)
  calendar_service.py  merge ICS feeds into a daily agenda
  email_inbox.py       read-only multi-account IMAP digest (inbound)
  briefing.py          morning brief from agenda + inbox
  todos.py             extract action items from email
  storage.py           SQLite (jobs, pipeline, to-dos, drafts, send log)
static/                index.html, style.css, app.js
data/resume.md         my resume — the source of truth for everything it writes
data/accounts.json     my calendars + email accounts (gitignored)
```

My resume lives in `data/resume.md` (already loaded with mine). Everything the
tool writes about me comes from there, so I keep it up to date.

## Ideas I might build next
- A morning brief that emails itself to me every day, so it just runs on its own.
- A conflict + travel-gap detector on the agenda (practice → class with no time to get there).
- Follow-up reminders that link the outreach tab to my inbox.
