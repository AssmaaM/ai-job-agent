"""
job_agent.py
------------
Core Agent: AutoJob AI Agent

This is the central orchestrator. It follows the agent pattern:

  User Input → Agent → Tools → Memory → Structured Output

The agent executes a fixed, sequential pipeline of tool calls:
  Step 1: Search for relevant jobs (job_search tool)
  Step 2: Score each job's relevance against the CV (job_matcher tool)
  Step 3: Generate application materials for top-ranked jobs (application_generator tool)
  Step 4: Store results in memory

Throughout execution, the agent emits structured log messages so the UI
can display real-time reasoning steps.
"""

import time
from typing import Generator, Optional

from tools.job_search           import search_jobs
from tools.job_matcher          import score_job
from tools.application_generator import generate_application
from utils.memory               import add_search, add_job_run, select_job


# ---------------------------------------------------------------------------
# Log Level Constants
# ---------------------------------------------------------------------------

LOG_INFO    = "info"
LOG_SUCCESS = "success"
LOG_WARNING = "warning"
LOG_ERROR   = "error"
LOG_STEP    = "step"


def _make_log(level: str, message: str) -> dict:
    """
    Create a structured log entry.

    Args:
        level   (str): One of LOG_INFO, LOG_SUCCESS, LOG_WARNING, LOG_ERROR, LOG_STEP.
        message (str): Human-readable log message.

    Returns:
        dict: {"level": str, "message": str, "timestamp": float}
    """
    return {
        "level":     level,
        "message":   message,
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Main Agent Entry Point
# ---------------------------------------------------------------------------

def run_agent(
    job_title:      str,
    location:       str,
    cv:             str,
    top_n:          int = 5,
    min_score:      int = 0,
    generate_apps:  bool = True,
    log_callback:   Optional[callable] = None,
) -> dict:
    """
    Run the full AutoJob AI Agent pipeline.

    Args:
        job_title     (str)     : Job title or keywords to search for.
        location      (str)     : Location filter (e.g., "Remote", "New York").
        cv            (str)     : Candidate's CV as plain text.
        top_n         (int)     : Max number of top-scored jobs to generate applications for.
        min_score     (int)     : Minimum relevance score (0-100) to include in results.
        generate_apps (bool)    : Whether to generate cover letters / LinkedIn messages.
        log_callback  (callable): Optional function called with each log dict in real time.

    Returns:
        dict: {
            "status"     : "success" | "error",
            "query"      : str,
            "location"   : str,
            "logs"       : list[dict],
            "jobs_found" : int,
            "jobs"       : list[dict],   ← enriched job dicts (score + application)
            "error"      : str | None,
        }
    """
    logs: list[dict] = []

    def log(level: str, message: str) -> None:
        """Append a log entry and optionally call the live callback."""
        entry = _make_log(level, message)
        logs.append(entry)
        if log_callback:
            log_callback(entry)

    # -------------------------------------------------------------------
    # Validate inputs
    # -------------------------------------------------------------------
    if not job_title.strip():
        return {
            "status":     "error",
            "query":      job_title,
            "location":   location,
            "logs":       logs,
            "jobs_found": 0,
            "jobs":       [],
            "error":      "Job title cannot be empty.",
        }

    if not cv.strip():
        return {
            "status":     "error",
            "query":      job_title,
            "location":   location,
            "logs":       logs,
            "jobs_found": 0,
            "jobs":       [],
            "error":      "CV text cannot be empty. Please provide your resume/CV.",
        }

    # -------------------------------------------------------------------
    # STEP 1 — Job Search
    # -------------------------------------------------------------------
    log(LOG_STEP, "Step 1 of 3: Searching for matching job listings...")
    log(LOG_INFO, f'Querying jobs for "{job_title}" in "{location or "Any Location"}"')

    try:
        raw_jobs = search_jobs(query=job_title, location=location)
    except Exception as e:
        log(LOG_ERROR, f"Job search failed: {str(e)}")
        return _error_result(job_title, location, logs, f"Job search failed: {str(e)}")

    if not raw_jobs:
        log(LOG_WARNING, "No jobs found matching your search. Try broader keywords or a different location.")
        return {
            "status":     "success",
            "query":      job_title,
            "location":   location,
            "logs":       logs,
            "jobs_found": 0,
            "jobs":       [],
            "error":      None,
        }

    log(LOG_SUCCESS, f"Found {len(raw_jobs)} job listing(s) matching your search.")

    # Persist search to memory
    add_search(job_title, location, len(raw_jobs))

    # -------------------------------------------------------------------
    # STEP 2 — AI Relevance Scoring
    # -------------------------------------------------------------------
    log(LOG_STEP, f"Step 2 of 3: Analysing CV relevance for {len(raw_jobs)} job(s)...")
    log(LOG_INFO, "Using GPT to evaluate skill alignment, experience match, and suitability...")

    scored_jobs = []

    for i, job in enumerate(raw_jobs, start=1):
        log(LOG_INFO, f"  [{i}/{len(raw_jobs)}] Scoring: {job['title']} @ {job['company']}")

        try:
            match_result = score_job(cv=cv, job_description=job.get("description", ""))
        except Exception as e:
            log(LOG_WARNING, f"  Scoring failed for {job['title']}: {str(e)}")
            match_result = {
                "score":       0,
                "explanation": "Scoring unavailable.",
                "strengths":   [],
                "gaps":        [],
            }

        enriched = {
            **job,
            "score":       match_result.get("score", 0),
            "explanation": match_result.get("explanation", ""),
            "strengths":   match_result.get("strengths", []),
            "gaps":        match_result.get("gaps", []),
        }
        scored_jobs.append(enriched)

    # Sort by score descending
    scored_jobs.sort(key=lambda j: j["score"], reverse=True)

    # Apply minimum score filter
    if min_score > 0:
        before = len(scored_jobs)
        scored_jobs = [j for j in scored_jobs if j["score"] >= min_score]
        log(LOG_INFO, f"Score filter (≥{min_score}): kept {len(scored_jobs)} of {before} job(s).")

    if not scored_jobs:
        log(LOG_WARNING, f"No jobs met the minimum score threshold of {min_score}.")
        return {
            "status":     "success",
            "query":      job_title,
            "location":   location,
            "logs":       logs,
            "jobs_found": 0,
            "jobs":       [],
            "error":      None,
        }

    # Summarise scoring results
    top_job   = scored_jobs[0]
    avg_score = sum(j["score"] for j in scored_jobs) // len(scored_jobs)
    log(LOG_SUCCESS,
        f"Scoring complete. Top match: \"{top_job['title']}\" @ {top_job['company']} "
        f"(score: {top_job['score']}/100). Average score: {avg_score}/100.")

    # -------------------------------------------------------------------
    # STEP 3 — Application Generation
    # -------------------------------------------------------------------
    jobs_for_apps = scored_jobs[:top_n]  # Only generate for top N jobs

    if generate_apps:
        log(LOG_STEP,
            f"Step 3 of 3: Generating personalised applications for top {len(jobs_for_apps)} job(s)...")

        for i, job in enumerate(jobs_for_apps, start=1):
            log(LOG_INFO,
                f"  [{i}/{len(jobs_for_apps)}] Writing cover letter & LinkedIn note for: "
                f"{job['title']} @ {job['company']}")

            try:
                app_result = generate_application(cv=cv, job=job)
                job["cover_letter"]     = app_result.get("cover_letter", "")
                job["linkedin_message"] = app_result.get("linkedin_message", "")
            except Exception as e:
                log(LOG_WARNING, f"  Application generation failed for {job['title']}: {str(e)}")
                job["cover_letter"]     = f"Generation failed: {str(e)}"
                job["linkedin_message"] = f"Generation failed: {str(e)}"

        # Jobs beyond top_n get empty application fields
        for job in scored_jobs[top_n:]:
            job["cover_letter"]     = ""
            job["linkedin_message"] = ""

        log(LOG_SUCCESS,
            f"Applications generated for {len(jobs_for_apps)} job(s).")
    else:
        log(LOG_INFO, "Application generation skipped (disabled by user).")
        for job in scored_jobs:
            job["cover_letter"]     = ""
            job["linkedin_message"] = ""

    # -------------------------------------------------------------------
    # Finalise & store in memory
    # -------------------------------------------------------------------
    log(LOG_SUCCESS,
        f"Agent run complete. "
        f"Returning {len(scored_jobs)} ranked job(s). "
        f"Top recommendation: \"{top_job['title']}\" at {top_job['company']}.")

    result = {
        "status":     "success",
        "query":      job_title,
        "location":   location,
        "logs":       logs,
        "jobs_found": len(scored_jobs),
        "jobs":       scored_jobs,
        "error":      None,
    }

    # Save the full run to memory
    add_job_run(result)

    # Auto-bookmark the top-ranked job
    if scored_jobs:
        select_job(scored_jobs[0])

    return result


# ---------------------------------------------------------------------------
# Streaming Generator (for live UI updates)
# ---------------------------------------------------------------------------

def run_agent_streaming(
    job_title:     str,
    location:      str,
    cv:            str,
    top_n:         int  = 5,
    min_score:     int  = 0,
    generate_apps: bool = True,
) -> Generator[dict, None, None]:
    """
    Generator wrapper around run_agent() that yields log entries in real time.

    Usage (in Streamlit or any streaming consumer):
        for event in run_agent_streaming(...):
            if event["type"] == "log":
                display(event["data"])
            elif event["type"] == "result":
                final_result = event["data"]

    Yields:
        dict: {"type": "log",    "data": log_dict}
              {"type": "result", "data": full_result_dict}
    """
    collected_logs: list[dict] = []

    def on_log(log_entry: dict) -> None:
        collected_logs.append(log_entry)

    # We cannot easily yield from inside the callback, so we buffer and flush
    # Instead, run_agent is called with the callback and result returned after
    result = run_agent(
        job_title=job_title,
        location=location,
        cv=cv,
        top_n=top_n,
        min_score=min_score,
        generate_apps=generate_apps,
        log_callback=on_log,
    )

    # Yield all collected logs first
    for log_entry in result.get("logs", []):
        yield {"type": "log", "data": log_entry}

    # Finally yield the full result
    yield {"type": "result", "data": result}


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------

def _error_result(query: str, location: str, logs: list, error_msg: str) -> dict:
    """Build a standardised error result dict."""
    return {
        "status":     "error",
        "query":      query,
        "location":   location,
        "logs":       logs,
        "jobs_found": 0,
        "jobs":       [],
        "error":      error_msg,
    }
