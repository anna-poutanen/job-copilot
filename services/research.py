"""Light-touch, public-source company research to ground the LLM's writing.

Sources used:
  - Wikipedia REST summary API (no key, public).
  - The company's own public website (homepage + /about), text only.
Everything is best-effort: if a source fails or is blocked, we skip it and
return whatever we could gather. Nothing here logs in or scrapes gated data.
"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "job-copilot/1.0 (personal job-search assistant)"}
TIMEOUT = 12


def _clean(text: str, limit: int = 1800) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit]


def wikipedia_summary(company: str) -> str:
    try:
        title = company.strip().replace(" ", "_")
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
            headers=HEADERS, timeout=TIMEOUT,
        )
        if r.ok:
            data = r.json()
            if data.get("type") == "standard" and data.get("extract"):
                return _clean(data["extract"])
    except Exception:
        pass
    return ""


def website_text(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    collected = []
    for path in ("", "/about"):
        try:
            r = requests.get(url.rstrip("/") + path, headers=HEADERS, timeout=TIMEOUT)
            if not r.ok:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            collected.append(soup.get_text(separator=" "))
        except Exception:
            continue
    return _clean(" ".join(collected), limit=2500)


def research_company(company: str, url: str = "") -> str:
    """Return a compact research brief, or a note if nothing was found."""
    parts = []
    wiki = wikipedia_summary(company)
    if wiki:
        parts.append(f"[Wikipedia] {wiki}")
    site = website_text(url) if url else ""
    if site:
        parts.append(f"[Company site] {site}")
    if not parts:
        return f"(No public research could be gathered for {company}. Writing from the job details only.)"
    return "\n\n".join(parts)
