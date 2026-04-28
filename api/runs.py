"""Run endpoints: create / list / snapshot / SSE stream / raw report."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Response
from sse_starlette.sse import EventSourceResponse

from .jobstore import JobState, get_store
from .models import (
    RunListItem,
    RunSnapshot,
    StartRunRequest,
    StartRunResponse,
)

router = APIRouter(prefix="/api", tags=["runs"])


def _snapshot(job: JobState) -> RunSnapshot:
    return RunSnapshot(
        job_id=job.job_id,
        target=job.target,
        max_candidates=job.max_candidates,
        use_af2_multimer=job.use_af2_multimer,
        dry_run=job.dry_run,
        status=job.status,
        current_step=job.current_step,
        log_lines=list(job.log_lines),
        decisions=list(job.decisions),
        error=job.error,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=job.result,
    )


@router.post("/runs", response_model=StartRunResponse)
async def start_run(req: StartRunRequest) -> StartRunResponse:
    store = get_store()
    loop = asyncio.get_running_loop()
    job = store.create(
        target=req.target,
        max_candidates=req.max_candidates,
        use_af2_multimer=req.use_af2_multimer,
        dry_run=req.dry_run,
        loop=loop,
    )
    store.submit(job)
    return StartRunResponse(job_id=job.job_id)


@router.get("/runs", response_model=list[RunListItem])
async def list_runs() -> list[RunListItem]:
    store = get_store()
    out: list[RunListItem] = []
    for job in store.list_recent():
        out.append(
            RunListItem(
                job_id=job.job_id,
                target=job.target,
                status=job.status,
                current_step=job.current_step,
                started_at=job.started_at,
                finished_at=job.finished_at,
                kept_count=(job.result.kept_count if job.result else None),
            )
        )
    return out


@router.get("/runs/{job_id}", response_model=RunSnapshot)
async def get_run(job_id: str) -> RunSnapshot:
    store = get_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _snapshot(job)


@router.get("/runs/{job_id}/report.md")
async def get_report(job_id: str) -> Response:
    store = get_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    md = job.result.report_md if job.result else ""
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{job.target}_{job.job_id}.md"'},
    )


@router.get("/runs/{job_id}/stream")
async def stream_run(job_id: str) -> EventSourceResponse:
    store = get_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def event_gen():
        # Replay current state so a late subscriber gets context.
        yield {
            "event": "snapshot",
            "data": json.dumps(_snapshot(job).model_dump(mode="json")),
        }
        # If already terminal, close immediately.
        if job.status in ("done", "error"):
            yield {"event": job.status, "data": json.dumps({"job_id": job.job_id})}
            return

        q = store.subscribe(job)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # keepalive comment — sse-starlette also sends pings, but explicit is fine
                    yield {"event": "ping", "data": "{}"}
                    if job.status in ("done", "error"):
                        return
                    continue
                yield {"event": msg["event"], "data": json.dumps(msg["data"])}
                if msg["event"] in ("done", "error"):
                    return
        finally:
            store.unsubscribe(job, q)

    return EventSourceResponse(event_gen())
