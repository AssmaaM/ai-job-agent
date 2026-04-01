"""
memory.py
---------
Simple persistent memory for the AutoJob AI Agent.
Stores previous searches and selected jobs in a local JSON file.
This allows the agent to "remember" past activity across sessions.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any

# Path to the persistent memory file (stored in data/ directory)
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "memory.json")


class Memory:
    """
    A lightweight persistent memory store backed by a local JSON file.
    Tracks search history and saved jobs for the user.
    """

    def __init__(self):
        """Load existing memory from disk, or initialize empty memory."""
        self.data = self._load()

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        """Read memory from the JSON file. Returns empty structure if not found."""
        try:
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data.setdefault("searches", [])
                    data.setdefault("job_runs", [])
                    data.setdefault("selected_jobs", [])
                    return data
        except (json.JSONDecodeError, IOError):
            pass  # Corrupted file – start fresh
        return {"searches": [], "job_runs": [], "selected_jobs": []}

    def _save(self) -> None:
        """Persist current memory to the JSON file."""
        try:
            os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[Memory] Warning: could not save memory – {e}")

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def save_search(self, query: str, location: str, results: Any) -> None:
        """
        Record a completed job search.

        Args:
            query:    Job title / keywords that were searched.
            location: Location string used in the search.
            results:  Either a list of jobs or an integer count.
        """
        if isinstance(results, int):
            results_count = results
            top_jobs = []
        else:
            results_list = results or []
            results_count = len(results_list)
            top_jobs = [
                f"{j.get('title', '')} @ {j.get('company', '')}"
                for j in results_list[:3]
            ]

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "query": query,
            "location": location if location else "Any",
            "result_count": results_count,
            "results_count": results_count,
            "top_jobs": top_jobs,
        }
        self.data.setdefault("searches", []).append(entry)
        self.data["searches"] = self.data["searches"][-20:]
        self._save()

    def save_job_run(self, run_result: Dict[str, Any]) -> None:
        """Save a full agent run for summary purposes."""
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "query": run_result.get("query", ""),
            "location": run_result.get("location", ""),
            "jobs_found": run_result.get("jobs_found", 0),
        }
        self.data.setdefault("job_runs", []).append(entry)
        self.data["job_runs"] = self.data["job_runs"][-50:]
        self._save()

    def save_selected_job(self, job: Dict) -> None:
        """
        Save a job the user has explicitly selected / bookmarked.

        Args:
            job: Job dictionary to save.
        """
        key = f"{job.get('title', '')}|{job.get('company', '')}"
        existing_keys = [
            f"{j.get('title', '')}|{j.get('company', '')}"
            for j in self.data.get("selected_jobs", [])
        ]
        if key not in existing_keys:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            job["saved_at"] = timestamp
            job["selected_at"] = timestamp
            self.data.setdefault("selected_jobs", []).append(job)
            self.data["selected_jobs"] = self.data["selected_jobs"][-50:]
            self._save()

    def get_history(self) -> List[Dict]:
        """Return all past search records (newest first)."""
        return list(reversed(self.data.get("searches", [])))

    def get_saved_jobs(self) -> List[Dict]:
        """Return all bookmarked / saved jobs."""
        return self.data.get("selected_jobs", [])

    def get_run_history(self) -> List[Dict]:
        """Return run history (newest first)."""
        return list(reversed(self.data.get("job_runs", [])))

    def get_summary(self) -> Dict[str, int]:
        """Return a small summary of memory contents."""
        return {
            "total_searches": len(self.data.get("searches", [])),
            "total_runs": len(self.data.get("job_runs", [])),
            "selected_jobs": len(self.data.get("selected_jobs", [])),
        }

    def clear_history(self) -> None:
        """Wipe all search history (keeps saved jobs intact)."""
        self.data["searches"] = []
        self._save()

    def clear_all(self) -> None:
        """Reset everything back to empty."""
        self.data = {"searches": [], "job_runs": [], "selected_jobs": []}
        self._save()


# ---------------------------------------------------------------------------
# Module-level convenience wrappers
# ---------------------------------------------------------------------------

_MEMORY = Memory()


def add_search(query: str, location: str, results: Any) -> None:
    _MEMORY.save_search(query, location, results)


def add_job_run(run_result: Dict[str, Any]) -> None:
    _MEMORY.save_job_run(run_result)


def select_job(job: Dict[str, Any]) -> None:
    _MEMORY.save_selected_job(job)


def get_search_history() -> List[Dict[str, Any]]:
    return _MEMORY.get_history()


def get_selected_jobs() -> List[Dict[str, Any]]:
    return _MEMORY.get_saved_jobs()


def get_memory_summary() -> Dict[str, int]:
    return _MEMORY.get_summary()


def reset_memory() -> None:
    _MEMORY.clear_all()
