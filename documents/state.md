# Implementation State

Last updated: 2026-04-17

## Completed

| File | Commit | Notes |
|------|--------|-------|
| `requirements.txt` | 42c33a1 | All pipeline deps; nvidia-nat install-from-source noted |
| `agent/tools/nim_cache.py` | 464bc67 | SHA-256 disk cache; all NIM calls route through here |
| `agent/tools/nim_tools.py` | 464bc67 | AlphaFold2, RFdiffusion, ProteinMPNN, AF2-Multimer, UniProt |
| `rag/ingest.py` | 464bc67 | PubMed → Chroma ingestion via Biopython Entrez |
| `agent/tools/scoring.py` | 771162d | pDockQ formula (Wallner lab Bryant 2022), 3 passing tests |
| `tests/test_scoring.py` | 771162d | Synthetic PDB + RCSB 1ZHH + missing-chain edge case |
| `modal_jobs/scoring_job.py` | 4a0b284 | Modal T4, `_score_single` helper, `.map()` batch, sort desc |
| `tests/test_scoring_job.py` | 4a0b284 | 5 tests: NIM mock, sequence order, map×1, sort verified |
| `rag/query.py` | bca33b5 | Chroma query interface; returns [] if not yet ingested |
| `config/workflow.yaml` | bca33b5 | NAT react_agent, nim_llm=llama-3.3-70b, 7 tools, system prompt |
| `agent/workflow.py` | bca33b5 | 7 @register_function tools with DECISION_A/B logging |

## Not Yet Built

| File | Description |
|------|-------------|
| `app.py` | CLI entry point: `python app.py --target EGFR` |
| `validate/egfr_run.py` | EGFR end-to-end validation |
| `validate/pcsk9_run.py` | PCSK9 end-to-end validation |
| `report/template.md` | Output report template |
| Modal Image config | `modal_jobs/scoring_job.py` needs `modal.Image.debian_slim().pip_install(...)` for remote execution — currently missing `image=` parameter on `@app.function` |

## Known Constraints

| Constraint | Detail |
|------------|--------|
| **RFdiffusion retry** | Retry payload MUST differ from original — nim_cache keys on SHA-256 of payload; identical inputs return cached result silently. Widen contigs by 20 residues per retry. |
| **pDockQ threshold** | > 0.23 = keep; < 0.23 = discard (Bryant et al. 2022 standard) |
| **pLDDT threshold** | > 70.0 = confident; < 70.0 = retry (backbone) or discard (complex) |
| **Credit budget** | ~17 NIM calls per fresh run; 0 on cache hits |
| **nat module** | v1.6.0 — `aiq` alias fully removed; use `nat.*` imports everywhere |
| **AF2-Multimer response** | Assumes `result["pdbs"][0]` is the PDB string; verify against live NIM response on first run |
| **Modal Image** | `score_candidate` container needs biopython, requests, python-dotenv, numpy installed via `modal.Image` — not yet configured, will fail on first `modal run` |
