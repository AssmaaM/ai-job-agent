"""
job_search.py
─────────────
Multi-source job scraper for the AutoJob AI Agent.

Sources tried in order (all real, live data — no mock fallback):
  1. RemoteOK   – public JSON API  (remote tech jobs)
  2. Remotive   – public JSON API  (remote jobs, all categories)
  3. Arbeitnow  – public JSON API  (remote + EU jobs)
  4. Jobicy     – public JSON API  (remote jobs)
  5. LinkedIn   – HTML / guest API (broad professional jobs)
  6. Indeed     – HTML scraping    (location-specific jobs)

Results from all successful sources are merged, deduplicated, and
capped at MAX_TOTAL_JOBS.  If zero sources return data, an empty
list is returned — the caller is responsible for surfacing that.
"""

import json
import os
import re
import time
import urllib.parse
from typing import Callable, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# ── Constants ────────────────────────────────────────────────────────────────

MAX_JOBS_PER_SOURCE = 5   # cap from each individual source
MAX_TOTAL_JOBS      = 8   # cap for the final merged list
REQUEST_TIMEOUT     = 12  # seconds before giving up on a request

# Realistic browser headers – reduces the chance of being blocked
_BROWSER_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection":      "keep-alive",
    "DNT":             "1",
}

_JSON_HEADERS: Dict[str, str] = {
    **_BROWSER_HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


# ── Utility helpers ──────────────────────────────────────────────────────────

def _clean_html(raw: str, max_chars: int = 900) -> str:
    """Strip HTML tags, collapse whitespace, and truncate."""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _is_remote(location: str) -> bool:
    """Return True when the user's location hint suggests remote work."""
    return location.strip().lower() in {"", "remote", "anywhere", "worldwide", "world"}


def _query_hits(text: str, query: str) -> bool:
    """
    STRICT relevance check: does *text* match the INTENT of the query?
    
    For queries like "AI Engineer", requires:
    1. AI-related keyword (ai, ml, machine learning, nlp, etc.)
    2. Role keyword (engineer, developer, scientist, architect, etc.)
    3. NOT excluded categories (sales, marketing, hr, finance, support, recruitment)
    
    For single-word queries, exact match is required.
    """
    stopwords = {"and", "or", "the", "a", "an", "for", "in", "at", "of", "to", "is", "are", "be", "that", "with"}
    words = [w for w in re.split(r"\W+", query.lower()) if w and w not in stopwords and len(w) > 2]
    
    if not words:
        return True  # can't filter – accept everything
    
    text_lower = text.lower()
    
    # For single-word queries, require exact match
    if len(words) == 1:
        return words[0] in text_lower
    
    # Keyword groups
    ai_keywords = {
        "ai", "artificial", "intelligence", "ml", "machine", "learning", 
        "deep", "neural", "nlp", "llm", "algorithm", "model",
        "analytics", "vision", "science"  # removed "data" (too broad), "computer" (matches CAD)
    }
    
    role_keywords = {
        "engineer", "developer", "scientist", "architect", "researcher",
        "analyst", "specialist", "expert", "lead", "principal"
    }
    
    # Exclusion keywords - roles that aren't technical engineering
    exclusions = {
        "sales", "marketing", "hr", "human", "recruitment", "recruiter",
        "finance", "financial", "support", "customer", "business",
        "manager", "liaison", "data security", "security analyst"  # security-focused roles
    }

    # Check for exclusions first - hard reject if primary role is non-technical
    for excl in exclusions:
        if excl in text_lower:
            return False  # Hard rejection for non-AI roles
    
    # For multi-word queries like "AI Engineer", require both AI and role keywords
    has_ai = any(kw in text_lower for kw in ai_keywords)
    has_role = any(kw in text_lower for kw in role_keywords)
    
    # Special handling for specific query patterns
    if "engineer" in query.lower() or "developer" in query.lower():
        # For "AI Engineer", "Python Developer", etc. - require both semantic matches
        # Also reject "Computer Aided X" patterns
        if "aided" in text_lower and "computer" in text_lower:
            return False
        return has_ai and has_role
    
    # For other queries, check keyword overlap (at least 50%)
    matches = sum(1 for w in words if w in text_lower)
    threshold = max(1, len(words) // 2)
    return matches >= threshold


def _location_matches(job_location: str, search_location: str) -> bool:
    """
    Check if job location matches search location.
    Handles "Remote" keyword and partial city name matching.
    """
    if not search_location or _is_remote(search_location):
        return True  # accept all locations if searching for "Remote" or any location
    
    job_loc = job_location.lower().strip()
    search_loc = search_location.lower().strip()
    
    # Exact match
    if search_loc in job_loc:
        return True
    
    # City name in country (e.g., "Paris, France")
    city = search_loc.split(",")[0].strip() if "," in search_loc else search_loc
    if city in job_loc:
        return True
    
    # Remote positions can match if user is OK with remote
    if "remote" in job_loc and ("remote" in search_loc or "anywhere" in search_loc):
        return True
    
    return False


def _deduplicate(jobs: List[Dict]) -> List[Dict]:
    """Remove near-duplicate entries (same title + company, case-insensitive)."""
    seen: set = set()
    unique: List[Dict] = []
    for job in jobs:
        key = (
            job.get("title",   "").lower().strip(),
            job.get("company", "").lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


# ── Source 1 – RemoteOK (public JSON API) ────────────────────────────────────

def _scrape_remoteok(query: str) -> List[Dict]:
    """
    Query the RemoteOK public API.
    Docs: https://remoteok.com/api  (no auth required)
    """
    jobs: List[Dict] = []
    try:
        resp = requests.get(
            "https://remoteok.com/api",
            headers=_JSON_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        # First element is always a legal-notice dict – skip it
        if data and isinstance(data[0], dict) and "legal" in data[0]:
            data = data[1:]

        for item in data:
            if len(jobs) >= MAX_JOBS_PER_SOURCE:
                break
            if not isinstance(item, dict):
                continue

            title    = item.get("position", "")
            company  = item.get("company",  "Unknown")
            location = item.get("location", "Remote") or "Remote"
            desc_raw = item.get("description", "")
            tags     = item.get("tags", []) or []
            url      = item.get("url", "")

            # Client-side relevance filter
            combined = f"{title} {company} {' '.join(tags)} {desc_raw}"
            if not _query_hits(combined, query):
                continue

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location,
                "description": _clean_html(desc_raw),
                "url":         url,
                "source":      "RemoteOK",
            })

    except Exception:
        pass  # caller handles empty list
    return jobs


# ── Source 2 – Remotive (public JSON API) ────────────────────────────────────

def _scrape_remotive(query: str, location: str = "") -> List[Dict]:
    """
    Query the Remotive public API.
    Docs: https://remotive.com/api/remote-jobs  (no auth required)
    
    Results are filtered for relevance: job title must match search query.
    """
    jobs: List[Dict] = []
    try:
        params = {"search": query, "limit": MAX_JOBS_PER_SOURCE * 2}
        resp = requests.get(
            "https://remotive.com/api/remote-jobs",
            params=params,
            headers=_JSON_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("jobs", [])

        for item in data:
            if len(jobs) >= MAX_JOBS_PER_SOURCE:
                break

            title    = item.get("title",        "")
            company  = item.get("company_name", "Unknown")
            location_val = item.get("candidate_required_location", "Remote") or "Remote"
            desc_raw = item.get("description",  "")
            url      = item.get("url",          "")

            # FILTERING: title must match query
            if not _query_hits(title + " " + desc_raw, query):
                continue

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location_val,
                "description": _clean_html(desc_raw),
                "url":         url,
                "source":      "Remotive",
            })

    except Exception:
        pass
    return jobs


# ── Source 3 – Arbeitnow (public JSON API) ───────────────────────────────────

def _scrape_arbeitnow(query: str, location: str) -> List[Dict]:
    """
    Query the Arbeitnow public API.
    Docs: https://arbeitnow.com/api/job-board-api  (no auth required)
    Supports `q` (keyword) and `location` query parameters.
    
    Results are filtered for relevance: job title and description must match search query,
    and location must match search location.
    """
    jobs: List[Dict] = []
    try:
        params: Dict[str, str] = {"q": query}
        if location and not _is_remote(location):
            params["location"] = location

        resp = requests.get(
            "https://arbeitnow.com/api/job-board-api",
            params=params,
            headers=_JSON_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])

        for item in data:
            if len(jobs) >= MAX_JOBS_PER_SOURCE:
                break

            title    = item.get("title",       "")
            company  = item.get("company_name","Unknown")
            loc      = item.get("location",    "Remote") or "Remote"
            desc_raw = item.get("description", "")
            url      = item.get("url",         "")
            remote   = item.get("remote",      False)

            if remote and "Remote" not in loc:
                loc = f"{loc} (Remote)"

            # STRICT FILTERING: title and description must match query, location must match
            if not _query_hits(title, query):
                continue  # skip if title doesn't match
            
            if not _query_hits(desc_raw, query):
                continue  # skip if description doesn't match
            
            if not _location_matches(loc, location):
                continue  # skip if location doesn't match

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    loc,
                "description": _clean_html(desc_raw),
                "url":         url,
                "source":      "Arbeitnow",
            })

    except Exception:
        pass
    return jobs


# ── Source 4 – Jobicy (public JSON API) ──────────────────────────────────────

def _scrape_jobicy(query: str, location: str = "") -> List[Dict]:
    """
    Query the Jobicy public API.
    Docs: https://jobicy.com/api/v2/remote-jobs  (no auth required)
    Supports `count` and `tag` parameters.
    
    Results are filtered for relevance: job title must match search query.
    """
    jobs: List[Dict] = []
    try:
        # `tag` = comma-separated job tags / keywords
        tag = query.replace(" ", ",").lower()
        params = {"count": MAX_JOBS_PER_SOURCE * 2, "tag": tag}

        resp = requests.get(
            "https://jobicy.com/api/v2/remote-jobs",
            params=params,
            headers=_JSON_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("jobs", [])

        for item in data:
            if len(jobs) >= MAX_JOBS_PER_SOURCE:
                break

            title    = item.get("jobTitle",    "")
            company  = item.get("companyName", "Unknown")
            location_val = item.get("jobGeo",      "Remote") or "Remote"
            desc_raw = item.get("jobExcerpt",  "") or item.get("jobDescription", "")
            url      = item.get("url",         "")

            # FILTERING: title and description must match query
            if not _query_hits(title + " " + desc_raw, query):
                continue

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location_val,
                "description": _clean_html(desc_raw),
                "url":         url,
                "source":      "Jobicy",
            })

    except Exception:
        pass
    return jobs


# ── Source 5 – LinkedIn Guest API (HTML) ─────────────────────────────────────

def _scrape_linkedin(query: str, location: str) -> List[Dict]:
    """
    Scrape LinkedIn's public guest-jobs endpoint (no auth required).
    LinkedIn uses aggressive bot-detection; this will succeed sometimes
    and return a 429 / CAPTCHA redirect other times.
    
    Results are filtered for relevance: job title must match search query,
    and location must match search location.
    """
    jobs: List[Dict] = []
    try:
        params = {
            "keywords": query,
            "location": location if location else "Worldwide",
            "start":    0,
        }
        url = (
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
            + urllib.parse.urlencode(params)
        )

        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code not in (200, 201):
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # LinkedIn's guest job-card class names (may change over time)
        cards = soup.find_all("li")

        for card in cards:
            if len(jobs) >= MAX_JOBS_PER_SOURCE:
                break

            # Title
            title_el = (
                card.find("h3", {"class": lambda c: c and "result-card__title" in c})
                or card.find("h3", {"class": lambda c: c and "base-search-card__title" in c})
                or card.find("h3")
            )
            # Company
            company_el = (
                card.find("h4", {"class": lambda c: c and "result-card__subtitle" in c})
                or card.find("h4", {"class": lambda c: c and "base-search-card__subtitle" in c})
                or card.find("h4")
            )
            # Location
            loc_el = (
                card.find("span", {"class": lambda c: c and "job-result-card__location" in c})
                or card.find("span", {"class": lambda c: c and "job-search-card__location" in c})
            )
            # Link
            link_el = card.find("a", href=True)

            title   = title_el.get_text(strip=True)   if title_el   else ""
            company = company_el.get_text(strip=True)  if company_el else "Unknown"
            loc     = loc_el.get_text(strip=True)      if loc_el     else location or "Unknown"
            href    = link_el["href"].split("?")[0]    if link_el    else ""

            if not title:
                continue

            # FILTERING: title must match query and location must match
            if not _query_hits(title, query):
                continue
            
            if not _location_matches(loc, location):
                continue

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    loc,
                "description": f"Apply on LinkedIn to read the full job description: {href}",
                "url":         href,
                "source":      "LinkedIn",
            })

    except Exception:
        pass
    return jobs


# ── Source 6 – Indeed (HTML scraping) ────────────────────────────────────────

def _scrape_indeed(query: str, location: str) -> List[Dict]:
    """
    Scrape Indeed's public job-search results page.
    Indeed uses Cloudflare and dynamic rendering; this approach works on
    basic HTML responses but may be blocked in some environments.
    """
    jobs: List[Dict] = []
    try:
        q   = urllib.parse.quote_plus(query)
        loc = urllib.parse.quote_plus(location if location else "remote")
        url = f"https://www.indeed.com/jobs?q={q}&l={loc}&limit=10&start=0"

        # Add a short delay to be a polite scraper
        time.sleep(1)

        resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Indeed renders job cards with multiple possible class structures
        cards = (
            soup.find_all("div", {"class": lambda c: c and "job_seen_beacon" in c})
            or soup.find_all("div", {"class": lambda c: c and "resultContent" in str(c)})
            or soup.find_all("td", {"class": "resultContent"})
        )

        for card in cards:
            if len(jobs) >= MAX_JOBS_PER_SOURCE:
                break
            try:
                # Title
                title_el = card.find("h2", {"class": lambda c: c and "jobTitle" in str(c)})
                title    = title_el.get_text(strip=True) if title_el else ""

                # Company
                company_el = (
                    card.find("span", {"class": lambda c: c and "companyName" in str(c)})
                    or card.find("a",  {"data-testid": "company-name"})
                    or card.find("span", {"class": "company"})
                )
                company = company_el.get_text(strip=True) if company_el else "Unknown"

                # Location
                loc_el = (
                    card.find("div", {"class": lambda c: c and "companyLocation" in str(c)})
                    or card.find("div", {"class": lambda c: c and "recJobLoc"  in str(c)})
                )
                loc = loc_el.get_text(strip=True) if loc_el else location or "Unknown"

                # Description snippet
                desc_el = (
                    card.find("div", {"class": lambda c: c and "job-snippet" in str(c)})
                    or card.find("div", {"class": "summary"})
                )
                desc = desc_el.get_text(" ", strip=True) if desc_el else ""

                # URL
                link_el = card.find("a", {"id": lambda i: i and "job_" in str(i)})
                href    = (
                    "https://www.indeed.com" + link_el["href"]
                    if link_el and link_el.get("href")
                    else "https://www.indeed.com"
                )

                if not title:
                    continue

                # FILTERING: title must match query and location must match
                if not _query_hits(title + " " + desc, query):
                    continue
                
                if not _location_matches(loc, location):
                    continue

                jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    loc,
                    "description": desc or "Visit Indeed for the full description.",
                    "url":         href,
                    "source":      "Indeed",
                })
            except Exception:
                continue

    except Exception:
        pass
    return jobs


# ── Public entry point ───────────────────────────────────────────────────────

def search_jobs(
    query:        str,
    location:     str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> List[Dict]:
    """
    Search for real job listings across six live sources.

    Args:
        query:        Job title / keywords entered by the user.
        location:     Desired work location (city, country, or "Remote").
        log_callback: Optional function called with each status message.
                      Useful for streaming logs to the UI in real time.

    Returns:
        A deduplicated list of job dicts from real APIs, each containing:
        title, company, location, description, url, source.
        Returns an empty list if all sources fail.
    """
    log = log_callback or (lambda _: None)
    all_jobs: List[Dict] = []

    log("🌐 Searching live job listing APIs…")

    # ── 1. RemoteOK ──────────────────────────────────────────────────────────
    log("🌐 [1/6] Querying RemoteOK API…")
    jobs = _scrape_remoteok(query)
    if jobs:
        log(f"   ✅ RemoteOK → {len(jobs)} job(s) found")
        all_jobs.extend(jobs)
    else:
        log("   ⚠️  RemoteOK → no results for this query")

    # ── 2. Remotive ──────────────────────────────────────────────────────────
    if len(all_jobs) < MAX_TOTAL_JOBS:
        log("🌐 [2/6] Querying Remotive API…")
        jobs = _scrape_remotive(query, location)
        if jobs:
            log(f"   ✅ Remotive → {len(jobs)} job(s) found")
            all_jobs.extend(jobs)
        else:
            log("   ⚠️  Remotive → no results for this query")

    # ── 3. Arbeitnow ─────────────────────────────────────────────────────────
    if len(all_jobs) < MAX_TOTAL_JOBS:
        log("🌐 [3/6] Querying Arbeitnow API…")
        jobs = _scrape_arbeitnow(query, location)
        if jobs:
            log(f"   ✅ Arbeitnow → {len(jobs)} job(s) found")
            all_jobs.extend(jobs)
        else:
            log("   ⚠️  Arbeitnow → no results for this query")

    # ── 4. Jobicy ────────────────────────────────────────────────────────────
    if len(all_jobs) < MAX_TOTAL_JOBS:
        log("🌐 [4/6] Querying Jobicy API…")
        jobs = _scrape_jobicy(query, location)
        if jobs:
            log(f"   ✅ Jobicy → {len(jobs)} job(s) found")
            all_jobs.extend(jobs)
        else:
            log("   ⚠️  Jobicy → no results for this query")

    # ── 5. LinkedIn ──────────────────────────────────────────────────────────
    if len(all_jobs) < MAX_TOTAL_JOBS:
        log("🌐 [5/6] Attempting LinkedIn guest-jobs scrape…")
        jobs = _scrape_linkedin(query, location)
        if jobs:
            log(f"   ✅ LinkedIn → {len(jobs)} job(s) found")
            all_jobs.extend(jobs)
        else:
            log("   ⚠️  LinkedIn → blocked or no results (common due to bot-detection)")

    # ── 6. Indeed ────────────────────────────────────────────────────────────
    if len(all_jobs) < MAX_TOTAL_JOBS:
        log("🌐 [6/6] Attempting Indeed HTML scrape…")
        jobs = _scrape_indeed(query, location)
        if jobs:
            log(f"   ✅ Indeed → {len(jobs)} job(s) found")
            all_jobs.extend(jobs)
        else:
            log("   ⚠️  Indeed → blocked or no results (common due to Cloudflare)")

    # ── Deduplicate & cap ─────────────────────────────────────────────────────
    unique = _deduplicate(all_jobs)
    
    # ── Apply strict semantic filtering ────────────────────────────────────────
    # For specific queries, filter results more aggressively
    query_lower = query.lower()
    
    # Check if this is a specific role query (AI Engineer, Python Developer, etc.)
    ROLE_KEYWORDS = {"engineer", "developer", "scientist", "architect", "researcher", "analyst"}
    DOMAIN_KEYWORDS = {"ai", "ml", "machine learning", "python", "java", "golang", "rust", "react", "vue"}
    
    is_specific_job_query = any(role in query_lower for role in ROLE_KEYWORDS)
    
    if is_specific_job_query:
        # Hard filter: job title must contain BOTH domain/role keywords
        filtered = []
        for job in unique:
            title_lower = job.get("title", "").lower()
            rejected_keywords = {"sales", "marketing", "hr", "recruiter", "finance", "support", "liaison"}
            
            # Hard reject if job is in excluded categories
            if any(kw in title_lower for kw in rejected_keywords):
                continue
            
            # For AI/ML queries, check for relevant keywords
            if "ai" in query_lower or "ml" in query_lower or "machine learning" in query_lower:
                has_ai_keyword = any(kw in title_lower for kw in ["ai", "ml", "machine", "learning", "neural", "nlp", "llm"])
                has_role_keyword = any(kw in title_lower for kw in ROLE_KEYWORDS)
                # Reject "Solution Architect CAD" patterns
                if "aided" in title_lower:
                    continue
                if not (has_ai_keyword and has_role_keyword):
                    continue
            
            filtered.append(job)
        
        final = filtered[:MAX_TOTAL_JOBS]
    else:
        final = unique[:MAX_TOTAL_JOBS]
    
    if final:
        sources_used = sorted({j["source"] for j in final})
        log(
            f"\n✅ Search complete — {len(final)} unique job(s) found "
            f"from: {', '.join(sources_used)}"
        )
    else:
        log(
            "\n❌ No jobs found across live sources. "
            "Try broader keywords, a different location, or check your internet connection."
        )

    return final
