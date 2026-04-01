"""
job_matcher.py
──────────────
Tool: AI-powered Job–CV relevance scorer.

Uses OpenAI (gpt-4o-mini) to compare a candidate's CV against a job
description and return:
  • score       – integer 0–100 reflecting how well the CV fits the role
  • explanation – 2-3 sentence human-readable explanation of the score

If OPENAI_API_KEY is not set or the API call fails, a lightweight
keyword-overlap heuristic is used as a graceful fallback so the app
stays fully functional in demo / offline scenarios.
"""

import json
import math
import os
import re
from typing import Dict

# ── OpenAI client (lazy import so the app doesn't crash without the key) ─────
try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    _openai_available = False


# ── Scoring prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior technical recruiter and career coach with deep expertise in
matching candidates to roles.  Your evaluations are honest, precise, and
actionable.
"""

_USER_PROMPT = """\
Analyse how well the candidate's CV matches the job description below.

Return ONLY a valid JSON object with exactly two keys:
  "score"       – integer between 0 and 100
  "explanation" – 2-3 sentences explaining the score, highlighting key
                  strengths and any significant gaps

CV:
{cv}

Job Description:
{job_description}
"""


# ── Keyword-overlap fallback ──────────────────────────────────────────────────

def _keyword_score(cv: str, job_description: str) -> Dict:
    """
    Fast, offline scoring based on keyword overlap.
    Used when OpenAI is unavailable.

    Returns the same {score, explanation} shape as the OpenAI path.
    """
    # Tokenise (lower-case words, remove stopwords / short tokens)
    stopwords = {
        "and","or","the","a","an","in","at","of","for","to","is","are","be",
        "with","on","we","you","your","our","their","have","has","will","can",
        "this","that","as","from","by","not","but","more","than","who","which",
    }

    def tokens(text: str):
        return {
            w for w in re.split(r"\W+", text.lower())
            if len(w) > 2 and w not in stopwords
        }

    cv_tokens  = tokens(cv)
    job_tokens = tokens(job_description)

    if not job_tokens:
        return {"score": 50, "explanation": "Could not parse job description."}

    overlap = cv_tokens & job_tokens
    ratio   = len(overlap) / math.sqrt(len(job_tokens))   # partial Jaccard variant
    score   = min(100, int(ratio * 60))                    # scale to 0-100

    # Build a human-readable explanation
    matched_words = sorted(overlap)[:8]
    if matched_words:
        matched_str = ", ".join(f"'{w}'" for w in matched_words)
        explanation = (
            f"Your CV shares {len(overlap)} keyword(s) with the job description "
            f"(e.g. {matched_str}), giving a similarity score of {score}/100.  "
            "Enable OpenAI for a deeper, context-aware analysis."
        )
    else:
        explanation = (
            f"Very few keyword overlaps were detected (score {score}/100).  "
            "The role may require skills not prominently featured in your CV, "
            "or the query terminology differs.  Enable OpenAI for richer analysis."
        )

    return {"score": score, "explanation": explanation}


# ── Main public function ──────────────────────────────────────────────────────

def score_job(cv: str, job_description: str) -> Dict:
    """
    Score how well *cv* matches *job_description*.

    Args:
        cv:              Raw text of the candidate's CV / résumé.
        job_description: Plain-text job description.

    Returns:
        dict with keys:
          "score"       (int, 0–100)
          "explanation" (str)
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    # ── Fallback path ─────────────────────────────────────────────────────────
    if not api_key or not _openai_available:
        return _keyword_score(cv, job_description)

    # ── OpenAI path ───────────────────────────────────────────────────────────
    try:
        client = OpenAI(api_key=api_key)

        # Truncate inputs to keep token cost low
        cv_snippet  = cv[:3000]
        job_snippet = job_description[:2000]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _USER_PROMPT.format(
                        cv=cv_snippet,
                        job_description=job_snippet,
                    ),
                },
            ],
        )

        result = json.loads(response.choices[0].message.content)

        # Validate and sanitise the response
        score = int(result.get("score", 0))
        score = max(0, min(100, score))           # clamp to [0, 100]
        explanation = str(result.get("explanation", "")).strip()

        if not explanation:
            explanation = "No explanation provided by the model."

        return {"score": score, "explanation": explanation}

    except json.JSONDecodeError:
        # Model returned non-JSON – fall back gracefully
        return _keyword_score(cv, job_description)

    except Exception as exc:
        # Network error, quota exceeded, invalid key, etc.
        fallback = _keyword_score(cv, job_description)
        fallback["explanation"] = (
            f"[OpenAI error: {type(exc).__name__}] " + fallback["explanation"]
        )
        return fallback
