"""Find software co-op / intern postings from PUBLIC, no-login job feeds.

Sources (all public JSON APIs, ToS-friendly, no scraping behind logins):
  - Remotive           https://remotive.com/api/remote-jobs
  - Arbeitnow          https://www.arbeitnow.com/api/job-board-api
  - Greenhouse boards  https://boards-api.greenhouse.io/v1/boards/<token>/jobs
  - Lever boards       https://api.lever.co/v0/postings/<token>
  - Adzuna (optional)  https://api.adzuna.com  (needs free APP_ID/APP_KEY)

Intentionally NOT included: LinkedIn / Indeed scraping. Those violate their
terms of service and break constantly; use their official search UIs instead.
"""
import re
import requests
import config

HEADERS = {"User-Agent": "job-copilot/1.0 (personal job-search assistant)"}
TIMEOUT = 15

# A posting must look like an early-career software role to be kept.
ROLE_HINTS = ("intern", "co-op", "coop", "co op", "new grad", "new-grad",
              "student", "university", "early career", "junior")
FIELD_HINTS = ("software", "developer", "engineer", "engineering", "programmer",
               "data", "full stack", "fullstack", "backend", "frontend", "ml", "ai")


def _matches(title: str, description: str, query: str) -> bool:
    hay = f"{title} {description}".lower()
    role_ok = any(h in hay for h in ROLE_HINTS)
    field_ok = any(h in hay for h in FIELD_HINTS)
    query_ok = query.lower() in hay if query else True
    return role_ok and field_ok and query_ok


def _loc_ok(location: str, wanted: str) -> bool:
    if not wanted:
        return True
    location = (location or "").lower()
    for token in re.split(r"[,/]| or ", wanted.lower()):
        token = token.strip()
        if token and token in location:
            return True
    # "remote" wanted should also match blank/worldwide postings
    if "remote" in wanted.lower() and ("remote" in location or not location):
        return True
    return False


def _norm(title, company, location, url, source, description):
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "").strip(),
        "url": (url or "").strip(),
        "source": source,
        "description": re.sub(r"<[^>]+>", " ", description or "").strip(),
    }


def from_remotive(query):
    out = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"search": query or "software intern"},
                         headers=HEADERS, timeout=TIMEOUT)
        for j in r.json().get("jobs", []):
            out.append(_norm(j.get("title"), j.get("company_name"),
                             j.get("candidate_required_location"), j.get("url"),
                             "Remotive", j.get("description")))
    except Exception as e:
        print("remotive error:", e)
    return out


def from_arbeitnow():
    out = []
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                         headers=HEADERS, timeout=TIMEOUT)
        for j in r.json().get("data", []):
            loc = j.get("location") or ("Remote" if j.get("remote") else "")
            out.append(_norm(j.get("title"), j.get("company_name"), loc,
                             j.get("url"), "Arbeitnow", j.get("description")))
    except Exception as e:
        print("arbeitnow error:", e)
    return out


def from_greenhouse(token):
    out = []
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
            params={"content": "true"}, headers=HEADERS, timeout=TIMEOUT)
        for j in r.json().get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            out.append(_norm(j.get("title"), token.capitalize(), loc,
                             j.get("absolute_url"), f"Greenhouse:{token}",
                             j.get("content", "")))
    except Exception as e:
        print(f"greenhouse {token} error:", e)
    return out


def from_lever(token):
    out = []
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{token}",
                         params={"mode": "json"}, headers=HEADERS, timeout=TIMEOUT)
        for j in r.json():
            loc = (j.get("categories") or {}).get("location", "")
            out.append(_norm(j.get("text"), token.capitalize(), loc,
                             j.get("hostedUrl"), f"Lever:{token}",
                             j.get("descriptionPlain", "")))
    except Exception as e:
        print(f"lever {token} error:", e)
    return out


def from_adzuna(query, location, country="ca"):
    out = []
    if not (config.ADZUNA_APP_ID and config.ADZUNA_APP_KEY):
        return out
    try:
        r = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
            params={
                "app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY,
                "results_per_page": 50, "what": query or "software intern",
                "where": location or "", "content-type": "application/json",
            }, headers=HEADERS, timeout=TIMEOUT)
        for j in r.json().get("results", []):
            out.append(_norm(j.get("title"), (j.get("company") or {}).get("display_name"),
                             (j.get("location") or {}).get("display_name"),
                             j.get("redirect_url"), "Adzuna", j.get("description")))
    except Exception as e:
        print("adzuna error:", e)
    return out


def search(query="", location="", sources=None, limit=60) -> dict:
    """Run selected sources, filter to early-career software roles, dedupe."""
    sources = sources or ["remotive", "arbeitnow", "greenhouse", "lever", "adzuna"]
    raw = []
    if "remotive" in sources:
        raw += from_remotive(query)
    if "arbeitnow" in sources:
        raw += from_arbeitnow()
    if "greenhouse" in sources:
        for t in config.GREENHOUSE_BOARDS:
            raw += from_greenhouse(t)
    if "lever" in sources:
        for t in config.LEVER_BOARDS:
            raw += from_lever(t)
    if "adzuna" in sources:
        raw += from_adzuna(query, location)

    seen, results = set(), []
    for j in raw:
        if not j["title"] or not j["url"]:
            continue
        if not _matches(j["title"], j["description"], query):
            continue
        if not _loc_ok(j["location"], location):
            continue
        key = f"{j['company']}|{j['title']}|{j['url']}".lower()
        if key in seen:
            continue
        seen.add(key)
        # trim description for transport
        j["description"] = j["description"][:1500]
        results.append(j)
        if len(results) >= limit:
            break
    return {"count": len(results), "checked": len(raw), "jobs": results}
