"""Merge multiple calendars into one agenda.

Uses ICS feed URLs (the "secret iCal address" Google Calendar gives you, the
"publish" link from Outlook, or a course-schedule export). ICS is read-only and
works across Google / Outlook / Apple / university systems without OAuth, which
keeps daily use frictionless. Recurring events (weekly practice, classes) are
expanded correctly and everything is normalized to your local timezone.
"""
import datetime as dt
from zoneinfo import ZoneInfo

import requests
import icalendar
import recurring_ical_events

import config

HEADERS = {"User-Agent": "job-copilot/1.0"}
TIMEOUT = 15


def _tz():
    try:
        return ZoneInfo(config.TIMEZONE)
    except Exception:
        return ZoneInfo("America/Toronto")


def _fetch(url: str) -> bytes | None:
    try:
        if url.startswith("webcal://"):
            url = "https://" + url[len("webcal://"):]
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.ok:
            return r.content
    except Exception as e:
        print("calendar fetch error:", e)
    return None


def _as_aware(value, tz):
    """Normalize a DTSTART/DTEND (date or datetime) to an aware datetime in tz."""
    if isinstance(value, dt.datetime):
        return value.astimezone(tz) if value.tzinfo else value.replace(tzinfo=tz)
    if isinstance(value, dt.date):  # all-day
        return dt.datetime(value.year, value.month, value.day, tzinfo=tz)
    return None


def _events_from(content, label, start, end, tz):
    out = []
    try:
        cal = icalendar.Calendar.from_ical(content)
        for e in recurring_ical_events.of(cal).between(start, end):
            raw = e.get("DTSTART").dt
            all_day = not isinstance(raw, dt.datetime)
            begin = _as_aware(raw, tz)
            end_raw = e.get("DTEND")
            finish = _as_aware(end_raw.dt, tz) if end_raw else None
            out.append({
                "calendar": label,
                "title": str(e.get("SUMMARY", "(no title)")),
                "location": str(e.get("LOCATION", "")) or "",
                "all_day": all_day,
                "start": begin.isoformat() if begin else "",
                "start_ts": begin.timestamp() if begin else 0,
                "end": finish.isoformat() if finish else "",
                "time_label": "all day" if all_day else (begin.strftime("%-I:%M %p") if begin else ""),
                "day": begin.strftime("%a %b %-d") if begin else "",
            })
    except Exception as ex:
        print(f"calendar parse error ({label}):", ex)
    return out


def agenda(days: int = 1) -> dict:
    """Merged events from today through `days` ahead, sorted chronologically."""
    tz = _tz()
    now = dt.datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + dt.timedelta(days=max(1, days))

    feeds = config.calendar_feeds()
    all_events, sources_ok = [], 0
    for feed in feeds:
        content = _fetch(feed["url"])
        if content is None:
            continue
        sources_ok += 1
        all_events += _events_from(content, feed.get("label", "Calendar"), start, end, tz)

    all_events.sort(key=lambda e: (e["start_ts"], not e["all_day"]))
    return {
        "timezone": config.TIMEZONE,
        "generated_at": now.isoformat(),
        "feeds_configured": len(feeds),
        "feeds_ok": sources_ok,
        "count": len(all_events),
        "events": all_events,
    }
