# CLAUDE.md — Agentic Drug Discovery Research Tool

## Project Overview

Autonomous protein binder design agent built on NVIDIA BioNeMo NIM APIs. Takes a protein target (UniProt ID or name) → outputs a structured research report with ranked binder candidates, pDockQ/pLDDT scores, 3D structure context, and literature-grounded rationale.

See `documents/architecture.md` for full system design.

---

## NIM API Credit Protection

**CRITICAL**: All NIM API calls MUST go through `agent/tools/nim_cache.py`. Direct calls to build.nvidia.com endpoints without caching are prohibited.

Free-tier credits are finite. Repeated debug runs against cached results cost $0. Bypassing the cache will exhaust credits within a session.

Applies to: AlphaFold2, RFdiffusion, ProteinMPNN, AlphaFold2-Multimer, Nemotron/Llama-3.3.

---

## Secrets

- API key lives in `.env` (never read, print, or reference its contents)
- `.gitignore` covers `.env`, `*.txt`, `.nim_cache/`
- Never hardcode API keys in any source file

---

## Development Rules

- Do not add pipeline code without the pre-build checklist being complete (see plan)
- Run validation against EGFR first before PCSK9
- pDockQ threshold: > 0.23 = likely binder; < 0.23 = discard
- pLDDT threshold: > 70 = confident prediction

---

## Commands

```bash
# Install dependencies
pip install aiq biopython chromadb sentence-transformers requests py3dmol

# Run agent
python app.py --target EGFR

# Ingest literature for a target
python rag/ingest.py --target EGFR --max-papers 100

# Validate
python validate/egfr_run.py
```

---

## Search

- Use Exa MCP for all research and documentation lookup
- Do NOT use built-in web search
