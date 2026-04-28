# Next Steps — Agentic Drug Discovery

_Last updated: 2026-04-27_

---

## Status

- ✅ Pipeline runs end-to-end for EGFR (dry-run verified)
- ✅ FastAPI backend + SSE streaming merged (PR #1)
- ✅ React/Vite frontend with live run dashboard merged (PR #1)
- ✅ RAG ingest done — `egfr_abstracts` (135 docs), `pcsk9_abstracts` (92 docs) in `.chroma/`

---

## Next session — pick up here

### 1. Live EGFR run with the UI open  ← do this first
Burns NIM credits but the cache makes re-runs free. This is the moment of truth
for the SSE event stream, log parsing, decision card rendering, scatter plot,
and 3Dmol viewer.

```bash
# terminal 1
uvicorn api.main:app --port 8000

# terminal 2
cd web && npm run dev    # http://localhost:5173
```

Then in the browser: New run → target `EGFR`, max candidates 5, AF2-Multimer
off, dry-run off → Run pipeline. Watch all four tabs (Live, Candidates,
Literature, Report). Verify:
- step strip advances 1 → 7
- DECISION_A and DECISION_B cards render
- scatter plot has dots in the green/amber zones
- Literature tab shows PMID accordion entries (RAG is now populated)
- Report tab renders + the .md download works
- 3Dmol viewer renders for at least one kept candidate (won't render for
  proxy-scored candidates with empty `pdb`)

### 2. PCSK9 validation run
Same flow as EGFR — second target per `CLAUDE.md`.

### 3. Run proxy calibration once
```bash
python validate/calibrate_proxy.py
```
Pulls 1IVO, 2P4E, 3BKX from RCSB and prints contact counts + pDockQ at
hypothetical pLDDT levels. Sanity-checks the discard threshold.

### 4. Periodic AF2-Multimer probe
```bash
python -m validate.probe_af2_multimer
```
Returns 0 if the hosted endpoint is alive. Run occasionally — if it ever
flips on, the circuit breaker uses real pDockQ automatically.

---

## Polish (only if showing this off)

- README screenshots / quickstart for the web UI
- Persist `JobStore` beyond process lifetime (currently in-memory; server
  restart wipes the sidebar)

---

## Known issues / decisions locked in

| Item | Decision |
|------|----------|
| AF2-Multimer 504 | Circuit breaker in `app.py` step 5 — falls back to MPNN proxy after first failure |
| Proxy pDockQ formula | `0.45 - (mpnn_score - 0.5) * 0.233`, clamped to [0.10, 0.45] |
| RFdiffusion retry (Decision A) | Must change contigs/hotspots per retry or cache returns same result (see memory) |
| ESMFold vs AlphaFold2 | Free tier uses ESMFold for monomer folding — AF2 single-chain also 504s |
| Job persistence | In-memory only — no disk store yet |
