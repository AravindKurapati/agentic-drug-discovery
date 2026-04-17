# Architecture: Agentic Drug Discovery Research Tool

## Overview

An autonomous AI research agent that accepts a protein target (UniProt ID or name) and produces a validated shortlist of designed protein binders with structural evidence and literature-grounded rationale — without human intervention mid-run.

Built on NVIDIA BioNeMo NIM APIs via `build.nvidia.com`, with the NeMo Agent Toolkit providing orchestration and agentic decision-making. Modal handles any local compute (pDockQ scoring). Chroma provides RAG over PubMed literature.

---

## System Diagram

```
Input: Protein target (name or UniProt ID)
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│                    NeMo Agent Toolkit                        │
│              (ReAct agent, YAML workflow config)             │
│                                                              │
│  [1] UniProt REST API ──► sequence (free, no credits)        │
│         │                                                    │
│         ▼                                                    │
│  [2] AlphaFold2 NIM ──► target PDB structure                 │
│      (skip if RCSB PDB has structure — saves credits)        │
│         │                                                    │
│         ▼                                                    │
│  [3] RFdiffusion NIM ──► N=5 binder backbones (PDB)         │
│         │                                                    │
│    ┌────▼────────────────────────────────┐                   │
│    │  DECISION A: backbone pLDDT < 70?  │                   │
│    │  Yes → adjust contigs/hotspots,    │                   │
│    │         retry (max 2x)             │                   │
│    │  No  → proceed                     │                   │
│    └────────────────────────────────────┘                   │
│         │                                                    │
│         ▼                                                    │
│  [4] ProteinMPNN NIM ──► amino acid sequences per backbone   │
│         │                                                    │
│         ▼                                                    │
│  [5] AlphaFold2-Multimer NIM ──► binder-target complex PDBs  │
│         │                                                    │
│         ▼                                                    │
│  [6] Modal (pDockQ scoring) ──► pLDDT + pDockQ per candidate │
│         │                                                    │
│    ┌────▼────────────────────────────────────────────┐      │
│    │  DECISION B: rank + filter candidates           │      │
│    │  Discard: pLDDT < 70 OR pDockQ < 0.23          │      │
│    │  Keep: top 3 by composite score                 │      │
│    │  LLM writes rationale for each kept/discarded   │      │
│    └──────────────────────────────────────────────────┘     │
│         │                                                    │
│         ▼                                                    │
│  [7] Chroma RAG ──► relevant PubMed abstracts per candidate  │
│         │                                                    │
│         ▼                                                    │
│  [8] Nemotron/Llama-3.3 NIM ──► structured research report  │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
Output: research_report_{target}_{timestamp}.md
        + 3D structure visualizations (py3Dmol HTML)
```

---

## Component Breakdown

### NIM APIs (build.nvidia.com)

| Model | Endpoint | Purpose |
|---|---|---|
| AlphaFold2 | `/protein-structure/alphafold2/predict-structure-from-sequence` | Target structure prediction |
| RFdiffusion | `/biology/ipd/rfdiffusion/generate` | Binder backbone generation |
| ProteinMPNN | `/biology/ipd/proteinmpnn/predict` | Sequence design for backbones |
| AlphaFold2-Multimer | `/protein-structure/alphafold2/multimer/predict-structure-from-sequences` | Complex structure prediction |
| Llama-3.3-70b-instruct | via NeMo Agent Toolkit nim_llm | Decision reasoning + report generation |

All calls go through `nim_cache.py` — disk cache keyed by SHA-256 of the input payload. Cache lives at `.nim_cache/` (gitignored).

### NeMo Agent Toolkit

- Version: v1.6.0
- Pattern: ReAct agent with custom tool functions
- Config: `config/workflow.yaml`
- Each pipeline step is a registered NeMo function tool
- Decision points use LLM reasoning to branch/retry

### Modal

- Used for: pDockQ scoring from PDB output (CPU job, no GPU needed)
- Function: `modal_jobs/scoring_job.py`
- Reuses Modal setup patterns from `../llm-serving-sec-filings/`

### RAG (Chroma + PubMed)

- Ingest: `rag/ingest.py` — fetches abstracts via Biopython Entrez API for target protein name
- Embed: `all-MiniLM-L6-v2` locally (avoids NIM credits for embeddings)
- Store: Chroma (pure Python, no server needed)
- Query: At Step 7, search by target name + binding domain keywords

---

## Scoring Metrics

### pLDDT (per-residue confidence)
- Source: AlphaFold2 and AlphaFold2-Multimer B-factor column in PDB output
- Threshold: > 70 = confident structure prediction
- Applied at: Decision A (backbone quality) + Decision B (complex quality)

### pDockQ (predicted DockQ — no reference structure needed)
- Standard metric for de novo binder screening (Björn Wallner lab)
- Formula: `pDockQ = 0.724 / (1 + exp(-0.052 * (mean_interface_pLDDT - 152.611))) + 0.018`
- Source: Computed from AF2-Multimer output by `modal_jobs/scoring_job.py`
- Threshold: > 0.23 = likely binder (literature standard)

---

## API Credit Strategy (Free Tier)

| NIM Call | Per Run | Mitigation |
|---|---|---|
| AlphaFold2 | 1 | Skip if RCSB PDB has structure; always cache |
| RFdiffusion | 5 | Max 5 backbones; cache all |
| ProteinMPNN | 5 | 1 sequence per backbone; cache all |
| AlphaFold2-Multimer | 5 | 1 per candidate; cache all |
| Llama-3.3 (report) | 1 | Single generation; cache all |
| **Total** | **~17 calls** | Cache hit = 0 credits |

On second+ runs against the same target: 0 credits consumed (all cached).

---

## Validation Targets

### EGFR (UniProt P00533)
- Known binders: EgA1/Nb7 nanobodies, cetuximab Fab
- Hotspot: domain III (residues ~334–504)
- Success: top candidate targets domain III; literature RAG returns EGFR nanobody papers

### PCSK9 (UniProt Q8NBP7)
- Known binders: evolocumab-derived peptides, adnectins
- Hotspot: EGF-AB domain interface (residues 367–692)

---

## File Map

```
agentic-drug-discovery/
├── .claude/
│   └── settings.json          # PreToolUse hooks (nim_cache check + secrets guard)
├── .gitignore                 # .env, *.txt, .nim_cache/
├── CLAUDE.md                  # Project-level guidance for this workspace
├── documents/
│   └── architecture.md        # This file
├── agent/
│   ├── workflow.py            # NeMo Agent Toolkit workflow definition
│   ├── tools/
│   │   ├── nim_cache.py       # Disk cache wrapper (SHA-256 keyed)
│   │   ├── nim_tools.py       # NIM API wrappers (all via nim_cache)
│   │   ├── scoring.py         # pDockQ formula + PDB parsing
│   │   ├── rag_tools.py       # Chroma query interface
│   │   └── viz_tools.py       # py3Dmol HTML output
│   └── prompts.py             # LLM decision + ranking prompts
├── rag/
│   ├── ingest.py              # PubMed ingestion → Chroma
│   └── query.py               # Chroma search interface
├── modal_jobs/
│   └── scoring_job.py         # Modal function: PDB → pLDDT + pDockQ
├── config/
│   └── workflow.yaml          # NeMo Agent Toolkit config
├── report/
│   └── template.md            # Output report template
├── app.py                     # CLI: python app.py --target EGFR
└── validate/
    ├── egfr_run.py
    └── pcsk9_run.py
```
