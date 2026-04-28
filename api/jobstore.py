"""In-process job store with thread-safe SSE fan-out.

Concurrency model:
- Pipeline runs in a worker thread (ThreadPoolExecutor).
- on_step() is invoked from that thread; it calls JobState.push_event().
- push_event() schedules queue.put_nowait via loop.call_soon_threadsafe so the
  asyncio side never sees cross-thread queue mutation.
- SSE endpoints subscribe by registering an asyncio.Queue; they unsubscribe in
  the finally block of the streaming response.
"""

from __future__ import annotations

import asyncio
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import RunResult, RunStatus

STEP_RE = re.compile(r"\[step (\d+)/\d+\] (\w+) \.\.\. (.+)")


@dataclass
class JobState:
    job_id: str
    target: str
    max_candidates: int
    use_af2_multimer: bool
    dry_run: bool
    status: RunStatus = "queued"
    current_step: int = 0
    log_lines: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    result: RunResult | None = None
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    _loop: asyncio.AbstractEventLoop | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)


class JobStore:
    def __init__(self, max_workers: int = 2) -> None:
        self._jobs: dict[str, JobState] = {}
        self._jobs_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pipeline")

    # ---- creation / lookup --------------------------------------------------
    def create(
        self,
        target: str,
        max_candidates: int,
        use_af2_multimer: bool,
        dry_run: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> JobState:
        job = JobState(
            job_id=uuid.uuid4().hex[:12],
            target=target,
            max_candidates=max_candidates,
            use_af2_multimer=use_af2_multimer,
            dry_run=dry_run,
        )
        job._loop = loop
        with self._jobs_lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobState | None:
        with self._jobs_lock:
            return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[JobState]:
        with self._jobs_lock:
            return sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)[:limit]

    # ---- pub/sub ------------------------------------------------------------
    def subscribe(self, job: JobState) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with job._lock:
            job.subscribers.append(q)
        return q

    def unsubscribe(self, job: JobState, q: asyncio.Queue) -> None:
        with job._lock:
            if q in job.subscribers:
                job.subscribers.remove(q)

    def push_event(self, job: JobState, event: str, data: dict[str, Any]) -> None:
        """Push an SSE event to every subscriber. Safe from any thread."""
        if job._loop is None:
            return
        with job._lock:
            subs = list(job.subscribers)
        for q in subs:
            try:
                job._loop.call_soon_threadsafe(q.put_nowait, {"event": event, "data": data})
            except RuntimeError:
                # loop closed
                pass

    # ---- pipeline runner ----------------------------------------------------
    def submit(self, job: JobState) -> None:
        self._executor.submit(self._run, job)

    def _run(self, job: JobState) -> None:
        from app import run_pipeline  # late import — avoid heavy deps at module load

        job.status = "running"
        self.push_event(job, "status", {"status": "running"})

        def on_step(msg: str) -> None:
            self._handle_log(job, msg)

        try:
            result = run_pipeline(
                target=job.target,
                max_candidates=job.max_candidates,
                dry_run=job.dry_run,
                use_af2_multimer=job.use_af2_multimer,
                on_step=on_step,
            )
            # Decision lines are also accumulated by _handle_log when present in
            # the log stream, but run_pipeline returns the canonical list in
            # result["decisions"]. Trust that one for the snapshot.
            decisions = result.get("decisions") or job.decisions
            job.decisions = decisions
            job.result = RunResult(
                target=job.target,
                candidates_evaluated=result.get("candidates_evaluated", 0),
                kept_count=result.get("kept_count", 0),
                scored=result.get("scored", []),
                literature=result.get("literature", []),
                report_md=result.get("report", ""),
                decisions=decisions,
            )
            job.status = "done"
            job.finished_at = datetime.utcnow()
            self.push_event(job, "done", {"job_id": job.job_id})
        except Exception as exc:  # noqa: BLE001 — top-level worker boundary
            job.status = "error"
            job.error = str(exc)
            job.finished_at = datetime.utcnow()
            self.push_event(job, "error", {"error": str(exc)})

    def _handle_log(self, job: JobState, msg: str) -> None:
        with job._lock:
            job.log_lines.append(msg)
        # Step parsing: track current_step from "[step N/7] name ... starting|done|..."
        m = STEP_RE.match(msg)
        if m:
            step_num = int(m.group(1))
            status = m.group(3)
            if "starting" in status:
                job.current_step = step_num
            elif "done" in status:
                job.current_step = step_num
        # Decision detection — also surface as its own SSE event for the UI rail
        if "DECISION_" in msg:
            with job._lock:
                job.decisions.append(msg)
            self.push_event(job, "decision", {"line": msg})
        self.push_event(
            job,
            "log",
            {"line": msg, "current_step": job.current_step},
        )


# Module-level singleton — FastAPI dependency injection wires this up.
_store: JobStore | None = None


def get_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
