# Next Steps — Agentic Drug Discovery

_Last updated: 2026-04-25_

---

## Status: Pipeline runs end-to-end for EGFR ✓

The full pipeline (ESMFold → RFdiffusion → ProteinMPNN → proxy scoring → report) completes
successfully. AF2-Multimer is confirmed unavailable on the NVIDIA free tier (persistent 504).
A circuit breaker was added so the pipeline falls back to proxy scoring immediately after the
first 504 rather than waiting 900 s per candidate.

---

## What to do next (in order)

### 1. Run RAG ingest for EGFR  ← do this first
```bash
python rag/ingest.py --target EGFR --max-papers 100
```
The literature section of every EGFR report is currently empty. This populates the ChromaDB
index so the report shows real supporting abstracts.

### 2. Re-run EGFR with literature populated
```bash
python app.py --target EGFR --max-candidates 5
```
Verify the Literature Context section now shows PMID entries.

### 3. Validate on PCSK9
```bash
python rag/ingest.py --target PCSK9 --max-papers 100
python app.py --target PCSK9 --max-candidates 5
```
EGFR was the smoke-test target. PCSK9 is the second validation target per CLAUDE.md.

### 4. Improve proxy pDockQ calibration (optional, nice-to-have)
The current proxy formula `0.45 - (mpnn_score - 0.5) * 0.233` is a linear rescale over
[0.5, 2.0]. It differentiates candidates correctly but the absolute values are uncalibrated
(not correlated with real pDockQ). If AF2-Multimer ever becomes available, run one batch
with real pDockQ to calibrate the proxy against ground truth.

### 5. AF2-Multimer free-tier status (check periodically)
The hosted endpoint `health.api.nvidia.com/v1/biology/deepmind/alphafold2-multimer` is
confirmed "Downloadable" (self-host intended). Check the NVIDIA API catalog occasionally
to see if hosted capacity improves. The circuit breaker and probe script are in place —
just re-run `python -m validate.probe_af2_multimer` to test.

---

## Known issues / decisions locked in

| Item | Decision |
|------|----------|
| AF2-Multimer 504 | Circuit breaker in `app.py` step 5 — falls back to MPNN proxy after first failure |
| Proxy pDockQ formula | `0.45 - (mpnn_score - 0.5) * 0.233`, clamped to [0.10, 0.45] |
| RFdiffusion retry (Decision A) | Must change contigs/hotspots per retry or cache returns same result (see memory) |
| ESMFold vs AlphaFold2 | Free tier uses ESMFold for monomer folding — AF2 single-chain also 504s |
