# Agentic Drug Discovery

Autonomous AI agent that takes a protein target and produces a ranked shortlist of designed protein binders with structural evidence and literature-grounded rationale — no human intervention mid-run.

---

## Pipeline

```
Input: Protein target (name or UniProt ID)
  |
  v
+---------------------------------------------------------+
|                    NeMo Agent Toolkit                    |
|              (ReAct agent, YAML workflow config)         |
|                                                          |
|  [1] UniProt REST API --> sequence (free, no credits)    |
|         |                                                |
|         v                                                |
|  [2] AlphaFold2 NIM --> target PDB structure             |
|      (skip if RCSB PDB has structure -- saves credits)   |
|         |                                                |
|         v                                                |
|  [3] RFdiffusion NIM --> N=5 binder backbones (PDB)      |
|         |                                                |
|    +----v--------------------------------------------+   |
|    |  DECISION A: backbone pLDDT < 70?              |   |
|    |  Yes -> adjust contigs/hotspots,               |   |
|    |         retry (max 2x)                         |   |
|    |  No  -> proceed                                |   |
|    +------------------------------------------------+   |
|         |                                                |
|         v                                                |
|  [4] ProteinMPNN NIM --> amino acid sequences per        |
|         backbone                                         |
|         |                                                |
|         v                                                |
|  [5] AlphaFold2-Multimer NIM --> binder-target complex   |
|         PDBs                                             |
|         |                                                |
|         v                                                |
|  [6] Modal (pDockQ scoring) --> pLDDT + pDockQ per       |
|         candidate                                        |
|         |                                                |
|    +----v------------------------------------------+     |
|    |  DECISION B: rank + filter candidates        |     |
|    |  Discard: pLDDT < 70 OR pDockQ < 0.23       |     |
|    |  Keep: top 3 by composite score              |     |
|    |  LLM writes rationale for each kept/discarded|     |
|    +-----------------------------------------------+     |
|         |                                                |
|         v                                                |
|  [7] Chroma RAG --> relevant PubMed abstracts per        |
|         candidate                                        |
|         |                                                |
|         v                                                |
|  [8] Nemotron/Llama-3.3 NIM --> structured research      |
|         report                                           |
+---------------------------------------------------------+
  |
  v
Output: research_report_{target}_{timestamp}.md
        + 3D structure visualizations (py3Dmol HTML)
```

---

## Stack

| Component | Role |
|---|---|
| NVIDIA BioNeMo NIM APIs | AlphaFold2, RFdiffusion, ProteinMPNN, AlphaFold2-Multimer, Llama-3.3 |
| NeMo Agent Toolkit v1.6.0 | ReAct orchestration, tool registration, YAML workflow config |
| Modal | pDockQ scoring from PDB output (CPU, no GPU needed) |
| Chroma | Vector store for PubMed abstract RAG |
| Biopython Entrez | PubMed ingestion |
| all-MiniLM-L6-v2 | Local embeddings (avoids NIM credits) |
| py3Dmol | 3D structure HTML visualizations |

All NIM calls go through `agent/tools/nim_cache.py` -- disk cache keyed by SHA-256 of input payload. Cache at `.nim_cache/` (gitignored). Second+ runs against the same target cost 0 credits.

---

## Quick Start

```bash
pip install aiq biopython chromadb sentence-transformers requests py3dmol

# Ingest literature for your target
python rag/ingest.py --target EGFR --max-papers 100

# Run the agent
python app.py --target EGFR
```

Output lands in `research_report_EGFR_{timestamp}.md` with accompanying HTML visualizations.

---

## Validation Targets

### EGFR (UniProt P00533)

- Known binders: EgA1/Nb7 nanobodies, cetuximab Fab
- Hotspot: domain III (residues 334-504)
- Pass criteria: top candidate targets domain III; RAG returns EGFR nanobody papers

### PCSK9 (UniProt Q8NBP7)

- Known binders: evolocumab-derived peptides, adnectins
- Hotspot: EGF-AB domain interface (residues 367-692)

Run validation scripts:

```bash
python validate/egfr_run.py
python validate/pcsk9_run.py
```

---

## File Map

```
agentic-drug-discovery/
+-- .claude/
|   +-- settings.json          # PreToolUse hooks (nim_cache check + secrets guard)
+-- .gitignore                 # .env, *.txt, .nim_cache/
+-- documents/
|   +-- architecture.md        # Full system design
+-- agent/
|   +-- workflow.py            # NeMo Agent Toolkit workflow definition
|   +-- tools/
|   |   +-- nim_cache.py       # Disk cache wrapper (SHA-256 keyed)
|   |   +-- nim_tools.py       # NIM API wrappers (all via nim_cache)
|   |   +-- scoring.py         # pDockQ formula + PDB parsing
|   |   +-- rag_tools.py       # Chroma query interface
|   |   +-- viz_tools.py       # py3Dmol HTML output
|   +-- prompts.py             # LLM decision + ranking prompts
+-- rag/
|   +-- ingest.py              # PubMed ingestion to Chroma
|   +-- query.py               # Chroma search interface
+-- modal_jobs/
|   +-- scoring_job.py         # Modal function: PDB to pLDDT + pDockQ
+-- config/
|   +-- workflow.yaml          # NeMo Agent Toolkit config
+-- report/
|   +-- template.md            # Output report template
+-- app.py                     # CLI: python app.py --target EGFR
+-- validate/
    +-- egfr_run.py
    +-- pcsk9_run.py
```

---

## Status

In active development -- not yet ready for use.
