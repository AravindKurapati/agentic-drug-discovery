// Mirror of api/models.py — keep in sync manually.

export type RunStatus = "queued" | "running" | "done" | "error";

export interface ScoredCandidate {
  candidate_id: string;
  pdockq: number;
  mean_interface_plddt: number;
  n_interface_contacts: number;
  pdb: string;
  binder_sequence: string | null;
  scoring_note: string | null;
  kept: boolean;
  discard_reason: string | null;
}

export interface LiteratureHit {
  pmid: string;
  title: string;
  abstract: string;
  distance: number | null;
}

export interface RunResult {
  target: string;
  candidates_evaluated: number;
  kept_count: number;
  scored: ScoredCandidate[];
  literature: LiteratureHit[];
  report_md: string;
  decisions: string[];
}

export interface RunSnapshot {
  job_id: string;
  target: string;
  max_candidates: number;
  use_af2_multimer: boolean;
  dry_run: boolean;
  status: RunStatus;
  current_step: number;
  total_steps: number;
  log_lines: string[];
  decisions: string[];
  error: string | null;
  started_at: string;
  finished_at: string | null;
  result: RunResult | null;
}

export interface RunListItem {
  job_id: string;
  target: string;
  status: RunStatus;
  current_step: number;
  total_steps: number;
  started_at: string;
  finished_at: string | null;
  kept_count: number | null;
}

export interface StartRunRequest {
  target: string;
  max_candidates: number;
  use_af2_multimer: boolean;
  dry_run: boolean;
}

export interface StartRunResponse {
  job_id: string;
}

export const STEP_NAMES = [
  "fetch_sequence",
  "run_alphafold2",
  "run_rfdiffusion",
  "run_proteinmpnn",
  "run_af2_multimer_batch",
  "query_literature",
  "generate_report",
] as const;

export const STEP_LABELS: Record<(typeof STEP_NAMES)[number], string> = {
  fetch_sequence: "Fetch sequence (UniProt)",
  run_alphafold2: "Predict target structure (ESMFold)",
  run_rfdiffusion: "Generate binder backbones (RFdiffusion)",
  run_proteinmpnn: "Design sequences (ProteinMPNN)",
  run_af2_multimer_batch: "Score complexes",
  query_literature: "Query literature (RAG)",
  generate_report: "Generate report",
};
