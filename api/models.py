"""Pydantic models — the contract the React frontend consumes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StartRunRequest(BaseModel):
    target: str = Field(..., description="UniProt ID or gene name (e.g. EGFR, P00533).")
    max_candidates: int = Field(5, ge=1, le=10)
    use_af2_multimer: bool = False
    dry_run: bool = False


class StartRunResponse(BaseModel):
    job_id: str


class ScoredCandidate(BaseModel):
    candidate_id: str
    pdockq: float
    mean_interface_plddt: float
    n_interface_contacts: int
    pdb: str = ""
    binder_sequence: str | None = None
    scoring_note: str | None = None
    kept: bool = True
    discard_reason: str | None = None


class LiteratureHit(BaseModel):
    pmid: str
    title: str
    abstract: str
    distance: float | None = None


class RunResult(BaseModel):
    target: str
    candidates_evaluated: int
    kept_count: int
    scored: list[ScoredCandidate]
    literature: list[LiteratureHit]
    report_md: str
    decisions: list[str]


RunStatus = Literal["queued", "running", "done", "error"]


class RunSnapshot(BaseModel):
    job_id: str
    target: str
    max_candidates: int
    use_af2_multimer: bool
    dry_run: bool
    status: RunStatus
    current_step: int
    total_steps: int = 7
    log_lines: list[str]
    decisions: list[str]
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    result: RunResult | None = None


class RunListItem(BaseModel):
    job_id: str
    target: str
    status: RunStatus
    current_step: int
    total_steps: int = 7
    started_at: datetime
    finished_at: datetime | None = None
    kept_count: int | None = None
