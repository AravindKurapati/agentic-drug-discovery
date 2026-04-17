# Modal Scoring Job + NAT Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `modal_jobs/scoring_job.py` (parallel AF2-Multimer + pDockQ via Modal `.map()`) then `agent/workflow.py` (seven NAT v1.6 pipeline tools + YAML config), in strict order — scoring_job committed before workflow starts.

**Architecture:** `scoring_job.py` extracts `_score_single()` as a testable helper wrapped by a `@app.function(gpu="T4")` Modal entry point; `score_candidates_batch()` calls `.map()` and sorts. `workflow.py` registers seven NAT tools using the `@register_function` / `FunctionBaseConfig` pattern from `nat` v1.6 (not `aiq`, which was removed in v1.6.0). Decision A (pLDDT < 70 → retry with wider contigs) and Decision B (filter pDockQ < 0.23, annotate kept/discarded) are enforced inside the tool functions and guided by the agent system prompt. All NIM calls route through `nim_tools.py` → `nim_cache.py`.

**Tech Stack:** Python 3.12, Modal, nvidia-nat v1.6 (`nat` module), Chroma, Biopython, pytest, unittest.mock

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `modal_jobs/__init__.py` | Create | Package marker |
| `modal_jobs/scoring_job.py` | Create | Modal `@app.function(gpu="T4")`, `_score_single`, `.map()` batch, sort |
| `tests/test_scoring_job.py` | Create | Mock NIM + Modal.map, verify .map() called once, results sorted desc |
| `rag/query.py` | Create | Chroma query interface (required by `query_literature` tool) |
| `config/workflow.yaml` | Create | NAT YAML: LLMs, 7 function declarations, react_agent with system prompt |
| `agent/workflow.py` | Create | 7 `@register_function` tool registrations with Decision A/B logging |
| `documents/state.md` | Create | Implementation state tracker (created last) |

---

## Task 1: `modal_jobs/scoring_job.py` — write failing test first

**Files:**
- Create: `tests/test_scoring_job.py`
- Create: `modal_jobs/__init__.py`
- Create: `modal_jobs/scoring_job.py`

- [ ] **Step 1.1: Write the failing test**

```python
# tests/test_scoring_job.py
"""
Tests for modal_jobs/scoring_job.py.
No real Modal or NIM calls — all external I/O is mocked.
"""
from unittest.mock import MagicMock, patch

# Minimal two-chain PDB: one residue per chain, 4 Å apart — within the 8 Å threshold.
_SYNTHETIC_PDB = (
    "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 75.00           C  \n"
    "ATOM      2  CA  ALA B   1       0.000   4.000   0.000  1.00 75.00           C  \n"
    "END\n"
)


def _af2_result(pdb: str = _SYNTHETIC_PDB) -> dict:
    return {"pdbs": [pdb]}


# ---------------------------------------------------------------------------
# _score_single
# ---------------------------------------------------------------------------

class TestScoreSingle:
    def test_calls_af2_with_target_then_binder(self):
        """af2_multimer_predict receives sequences=[target, binder] in that order."""
        candidate = {
            "candidate_id": "c1",
            "binder_sequence": "ACDE",
            "target_sequence": "MNPQ",
        }
        with patch(
            "modal_jobs.scoring_job.af2_multimer_predict",
            return_value=_af2_result(),
        ) as mock_af2:
            from modal_jobs.scoring_job import _score_single
            _score_single(candidate)

        mock_af2.assert_called_once_with(sequences=["MNPQ", "ACDE"])

    def test_result_has_required_keys(self):
        """Result dict contains candidate_id, pdockq, mean_interface_plddt, n_interface_contacts, pdb."""
        candidate = {"candidate_id": "c1", "binder_sequence": "ACDE", "target_sequence": "MNPQ"}
        with patch(
            "modal_jobs.scoring_job.af2_multimer_predict",
            return_value=_af2_result(),
        ):
            from modal_jobs.scoring_job import _score_single
            result = _score_single(candidate)

        assert result["candidate_id"] == "c1"
        for key in ("pdockq", "mean_interface_plddt", "n_interface_contacts", "pdb"):
            assert key in result, f"Missing key: {key}"
        assert isinstance(result["pdockq"], float)

    def test_pdb_field_is_raw_string_from_af2_response(self):
        """result['pdb'] is the first PDB string from the AF2-Multimer response."""
        candidate = {"candidate_id": "c2", "binder_sequence": "A", "target_sequence": "M"}
        with patch(
            "modal_jobs.scoring_job.af2_multimer_predict",
            return_value=_af2_result(_SYNTHETIC_PDB),
        ):
            from modal_jobs.scoring_job import _score_single
            result = _score_single(candidate)

        assert result["pdb"] == _SYNTHETIC_PDB


# ---------------------------------------------------------------------------
# score_candidates_batch
# ---------------------------------------------------------------------------

class TestScoreCandidatesBatch:
    def test_map_called_once_with_full_list(self):
        """score_candidates_batch calls .map() once with the full candidates list, not per-item."""
        candidates = [
            {"candidate_id": "low",  "binder_sequence": "AA", "target_sequence": "MM"},
            {"candidate_id": "high", "binder_sequence": "CC", "target_sequence": "NN"},
        ]
        low  = {"candidate_id": "low",  "pdockq": 0.10, "mean_interface_plddt": 55.0,
                "n_interface_contacts": 2, "pdb": ""}
        high = {"candidate_id": "high", "pdockq": 0.45, "mean_interface_plddt": 82.0,
                "n_interface_contacts": 9, "pdb": ""}

        mock_map = MagicMock(return_value=iter([low, high]))
        with patch("modal_jobs.scoring_job.score_candidate") as mock_fn:
            mock_fn.map = mock_map
            from modal_jobs.scoring_job import score_candidates_batch
            results = score_candidates_batch(candidates)

        mock_map.assert_called_once_with(candidates)
        assert len(results) == 2

    def test_results_sorted_by_pdockq_descending(self):
        """Results come back highest pDockQ first regardless of input order."""
        candidates = [
            {"candidate_id": "low",  "binder_sequence": "AA", "target_sequence": "MM"},
            {"candidate_id": "high", "binder_sequence": "CC", "target_sequence": "NN"},
        ]
        low  = {"candidate_id": "low",  "pdockq": 0.10, "mean_interface_plddt": 55.0,
                "n_interface_contacts": 2, "pdb": ""}
        high = {"candidate_id": "high", "pdockq": 0.45, "mean_interface_plddt": 82.0,
                "n_interface_contacts": 9, "pdb": ""}

        mock_map = MagicMock(return_value=iter([low, high]))
        with patch("modal_jobs.scoring_job.score_candidate") as mock_fn:
            mock_fn.map = mock_map
            from modal_jobs.scoring_job import score_candidates_batch
            results = score_candidates_batch(candidates)

        assert results[0]["candidate_id"] == "high"
        assert results[1]["candidate_id"] == "low"
        assert results[0]["pdockq"] >= results[1]["pdockq"]
```

- [ ] **Step 1.2: Run test — expect ModuleNotFoundError**

```bash
cd D:/Aru/NYU/agentic-drug-discovery
python -m pytest tests/test_scoring_job.py -v
```

Expected: `ModuleNotFoundError: No module named 'modal_jobs'`

- [ ] **Step 1.3: Create `modal_jobs/__init__.py`**

```python
# modal_jobs/__init__.py
```

(empty file)

- [ ] **Step 1.4: Write `modal_jobs/scoring_job.py`**

```python
"""
modal_jobs/scoring_job.py — Parallel AF2-Multimer + pDockQ scoring via Modal.

Each candidate gets its own Modal invocation (one NIM call). Results are
returned sorted by pDockQ descending.
"""

import modal

from agent.tools.nim_tools import af2_multimer_predict
from agent.tools.scoring import score_complex

app = modal.App("drug-discovery-scoring")


def _score_single(candidate: dict) -> dict:
    """
    Score one candidate: call AF2-Multimer NIM → parse PDB → compute pDockQ.

    candidate keys:
        candidate_id    : str — opaque identifier
        binder_sequence : str — designed binder amino acid sequence
        target_sequence : str — target protein amino acid sequence

    Returns dict with: candidate_id, pdockq, mean_interface_plddt,
                       n_interface_contacts, pdb
    """
    result = af2_multimer_predict(
        sequences=[candidate["target_sequence"], candidate["binder_sequence"]]
    )
    pdb_str = result["pdbs"][0]
    scores = score_complex(pdb_str, binder_chain="B", target_chain="A")
    return {
        "candidate_id": candidate["candidate_id"],
        "pdockq": scores["pdockq"],
        "mean_interface_plddt": scores["mean_interface_plddt"],
        "n_interface_contacts": scores["n_interface_contacts"],
        "pdb": pdb_str,
    }


@app.function(gpu="T4")
def score_candidate(candidate: dict) -> dict:
    """Modal entry point — one isolated container invocation per candidate."""
    return _score_single(candidate)


def score_candidates_batch(candidates: list[dict]) -> list[dict]:
    """
    Score all candidates in parallel via Modal .map(), return sorted by pDockQ desc.

    Dispatches one Modal container per candidate. Safe to call from any Python
    process — Modal handles remote execution and result collection.
    """
    results = list(score_candidate.map(candidates))
    return sorted(results, key=lambda r: r["pdockq"], reverse=True)
```

- [ ] **Step 1.5: Run tests — expect all passing**

```bash
python -m pytest tests/test_scoring_job.py -v
```

Expected:
```
tests/test_scoring_job.py::TestScoreSingle::test_calls_af2_with_target_then_binder    PASSED
tests/test_scoring_job.py::TestScoreSingle::test_result_has_required_keys             PASSED
tests/test_scoring_job.py::TestScoreSingle::test_pdb_field_is_raw_string_from_af2_response PASSED
tests/test_scoring_job.py::TestScoreCandidatesBatch::test_map_called_once_with_full_list   PASSED
tests/test_scoring_job.py::TestScoreCandidatesBatch::test_results_sorted_by_pdockq_descending PASSED

5 passed
```

- [ ] **Step 1.6: Run the full test suite to confirm no regressions**

```bash
python -m pytest tests/ -v
```

Expected: all prior scoring tests (3) + new tests (5) = 8 passed.

- [ ] **Step 1.7: Commit scoring_job**

```bash
git add modal_jobs/__init__.py modal_jobs/scoring_job.py tests/test_scoring_job.py
git commit -m "feat: add Modal scoring job wrapping AF2-Multimer + pDockQ with parallel .map()"
```

---

## Task 2: `rag/query.py` — Chroma query interface

Required by the `query_literature` tool in `workflow.py`. No unit test (Chroma is stateful; requires a prior `rag/ingest.py` run).

**Files:**
- Create: `rag/query.py`

- [ ] **Step 2.1: Write `rag/query.py`**

```python
"""
rag/query.py — Query the Chroma vector DB built by rag/ingest.py.
"""

from pathlib import Path

import chromadb

CHROMA_PATH = Path(__file__).resolve().parents[1] / ".chroma"


def query_abstracts(target: str, query_text: str, n_results: int = 5) -> list[dict]:
    """
    Search the Chroma collection for `target` with `query_text`.

    Returns [{pmid, title, abstract, distance}] ordered by relevance.
    Returns [] if the collection has not been ingested yet.
    """
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection_name = f"{target.lower()}_abstracts"
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return []

    results = collection.query(query_texts=[query_text], n_results=n_results)
    docs      = results.get("documents", [[]])[0]
    metas     = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    return [
        {
            "pmid": m.get("pmid", ""),
            "title": m.get("title", ""),
            "abstract": d,
            "distance": dist,
        }
        for d, m, dist in zip(docs, metas, distances)
    ]
```

- [ ] **Step 2.2: (No commit yet — commit together with workflow files in Task 4)**

---

## Task 3: `config/workflow.yaml`

**Files:**
- Create: `config/workflow.yaml`

- [ ] **Step 3.1: Write `config/workflow.yaml`**

```yaml
# config/workflow.yaml — NeMo Agent Toolkit (nat v1.6) workflow config
#
# Run:  nat run --config_file config/workflow.yaml --input "EGFR"
# Serve: nat serve --config_file config/workflow.yaml

general:
  use_uvloop: false

functions:
  fetch_sequence:
    _type: fetch_sequence

  run_alphafold2:
    _type: run_alphafold2

  run_rfdiffusion:
    _type: run_rfdiffusion
    n_designs: 5
    diffusion_steps: 15

  run_proteinmpnn:
    _type: run_proteinmpnn

  run_af2_multimer_batch:
    _type: run_af2_multimer_batch

  query_literature:
    _type: query_literature
    n_results: 5

  generate_report:
    _type: generate_report

llms:
  nim_llm:
    _type: nim
    model_name: meta/llama-3.3-70b-instruct
    temperature: 0.0
    max_tokens: 4096

workflow:
  _type: react_agent
  tool_names:
    - fetch_sequence
    - run_alphafold2
    - run_rfdiffusion
    - run_proteinmpnn
    - run_af2_multimer_batch
    - query_literature
    - generate_report
  llm_name: nim_llm
  verbose: true
  parse_agent_response_max_retries: 3
  system_prompt: |
    You are a protein binder design agent. Given a protein target (UniProt ID or name),
    execute the full pipeline in this exact order:

    1. fetch_sequence(uniprot_id) → amino acid sequence string
    2. run_alphafold2(sequence) → target PDB string
    3. run_rfdiffusion(target_pdb, contigs, hotspot_res="")
       - Initial contigs: "B50-100/0 A1-300"
       - Returns JSON: {"pdbs": [...], "mean_plddt": float}
       DECISION A: If mean_plddt < 70, adjust contigs by widening binder length
       range by 20 residues (e.g. "B50-100" → "B70-120"), then retry run_rfdiffusion.
       Maximum 2 retries. Each retry MUST use different contigs from previous call.
       Log each decision: "DECISION_A: [PASS|RETRY_1|RETRY_2] mean_plddt=X.X contigs=..."
    4. run_proteinmpnn(backbones_json) → JSON list of {backbone_idx, sequence}
    5. Build candidates list: for each {backbone_idx, sequence}, create
       {candidate_id: "cand_{backbone_idx}", binder_sequence: sequence, target_sequence: <from step 1>}
       Call run_af2_multimer_batch(JSON with "candidates" list and "pdockq_threshold": 0.23)
       Returns scored candidates annotated with "kept" bool and "discard_reason".
       DECISION B is applied inside run_af2_multimer_batch automatically.
       Log: "DECISION_B: kept N, discarded M"
    6. query_literature(JSON with "target" and "query_text": "<target> protein binder design")
    7. generate_report(JSON with "target", "scored_candidates", "literature", "decision_log")
       where decision_log is all DECISION_A and DECISION_B log lines concatenated.

    All NIM calls are disk-cached — repeat runs cost zero credits.
    Never call NIM APIs directly. Always use the provided tools.
```

- [ ] **Step 3.2: (No commit yet — commit together with workflow.py in Task 4)**

---

## Task 4: `agent/workflow.py` — seven NAT tool registrations

**NAT v1.6 import paths (confirmed):**
```python
from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
```

**Key rule (from NAT docs):** The inner callable (`_fn`) must be **defined inside** the `@register_function` coroutine body. Do not define inner callables at module level.

**Files:**
- Create: `agent/workflow.py`

- [ ] **Step 4.1: Write `agent/workflow.py`**

```python
"""
agent/workflow.py — NeMo Agent Toolkit (nat v1.6) tool registrations.

Seven pipeline steps registered as nat functions. The ReAct agent in
config/workflow.yaml calls them in order and handles Decision A/B reasoning.
All NIM calls go through nim_tools.py → nim_cache.py. workflow.py never
calls NIM APIs directly.
"""

import json
import logging

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: fetch_sequence
# ---------------------------------------------------------------------------

class FetchSequenceConfig(FunctionBaseConfig, name="fetch_sequence"):
    description: str = (
        "Fetch the amino acid sequence for a UniProt accession ID. "
        "Input: uniprot_id (str). Returns the sequence as a plain string."
    )


@register_function(config_type=FetchSequenceConfig)
async def fetch_sequence_fn(config: FetchSequenceConfig, builder: Builder):
    from agent.tools.nim_tools import uniprot_fetch_sequence

    async def _fn(uniprot_id: str) -> str:
        seq = uniprot_fetch_sequence(uniprot_id)
        logger.info("fetch_sequence: %s → %d residues", uniprot_id, len(seq))
        return seq

    yield FunctionInfo.from_fn(_fn, description=config.description)


# ---------------------------------------------------------------------------
# Tool 2: run_alphafold2
# ---------------------------------------------------------------------------

class RunAlphaFold2Config(FunctionBaseConfig, name="run_alphafold2"):
    description: str = (
        "Predict target protein 3D structure from its amino acid sequence "
        "using AlphaFold2 NIM. Input: sequence (str). Returns a PDB string."
    )


@register_function(config_type=RunAlphaFold2Config)
async def run_alphafold2_fn(config: RunAlphaFold2Config, builder: Builder):
    from agent.tools.nim_tools import alphafold2_predict

    async def _fn(sequence: str) -> str:
        result = alphafold2_predict(sequence)
        pdb = result["pdbs"][0]
        logger.info("run_alphafold2: structure predicted (%d chars)", len(pdb))
        return pdb

    yield FunctionInfo.from_fn(_fn, description=config.description)


# ---------------------------------------------------------------------------
# Tool 3: run_rfdiffusion
# ---------------------------------------------------------------------------

class RunRFDiffusionConfig(FunctionBaseConfig, name="run_rfdiffusion"):
    n_designs: int = 5
    diffusion_steps: int = 15
    description: str = (
        "Generate protein binder backbone structures using RFdiffusion NIM. "
        "Inputs: target_pdb (str), contigs (str), hotspot_res (str, optional). "
        "Returns JSON string: {\"pdbs\": [pdb1, ...], \"mean_plddt\": float}. "
        "Decision A: if mean_plddt < 70, caller must widen contigs and retry (max 2x)."
    )


@register_function(config_type=RunRFDiffusionConfig)
async def run_rfdiffusion_fn(config: RunRFDiffusionConfig, builder: Builder):
    from agent.tools.nim_tools import rfdiffusion_generate

    async def _fn(target_pdb: str, contigs: str, hotspot_res: str = "") -> str:
        result = rfdiffusion_generate(
            input_pdb=target_pdb,
            contigs=contigs,
            hotspot_res=hotspot_res,
            diffusion_steps=config.diffusion_steps,
        )
        backbones: list[str] = result.get("pdbs", [])
        mean_plddt: float = result.get("mean_plddt", 0.0)
        decision = "PASS" if mean_plddt >= 70.0 else "RETRY_NEEDED"
        logger.info(
            "DECISION_A: %s mean_plddt=%.1f contigs=%s n_backbones=%d",
            decision, mean_plddt, contigs, len(backbones),
        )
        return json.dumps({"pdbs": backbones, "mean_plddt": mean_plddt})

    yield FunctionInfo.from_fn(_fn, description=config.description)


# ---------------------------------------------------------------------------
# Tool 4: run_proteinmpnn
# ---------------------------------------------------------------------------

class RunProteinMPNNConfig(FunctionBaseConfig, name="run_proteinmpnn"):
    description: str = (
        "Design amino acid sequences for binder backbones using ProteinMPNN NIM. "
        "Input: backbones_json (str) — JSON list of backbone PDB strings. "
        "Returns JSON list of {backbone_idx (int), sequence (str)} dicts."
    )


@register_function(config_type=RunProteinMPNNConfig)
async def run_proteinmpnn_fn(config: RunProteinMPNNConfig, builder: Builder):
    from agent.tools.nim_tools import proteinmpnn_predict

    async def _fn(backbones_json: str) -> str:
        backbones: list[str] = json.loads(backbones_json)
        candidates = []
        for idx, pdb in enumerate(backbones):
            result = proteinmpnn_predict(pdb)
            seq = result.get("sequences", [""])[0]
            candidates.append({"backbone_idx": idx, "sequence": seq})
            logger.info("run_proteinmpnn: backbone %d → %d residues", idx, len(seq))
        return json.dumps(candidates)

    yield FunctionInfo.from_fn(_fn, description=config.description)


# ---------------------------------------------------------------------------
# Tool 5: run_af2_multimer_batch  (calls Modal scoring job)
# ---------------------------------------------------------------------------

class RunAF2MultiBatchConfig(FunctionBaseConfig, name="run_af2_multimer_batch"):
    description: str = (
        "Score all binder candidates with AF2-Multimer + pDockQ via Modal. "
        "Input: input_json (str) — JSON with keys: "
        "  'candidates': list of {candidate_id, binder_sequence, target_sequence}, "
        "  'pdockq_threshold': float (default 0.23), "
        "  'plddt_threshold': float (default 70.0). "
        "Returns JSON list of scored candidates sorted by pDockQ descending. "
        "Each candidate is annotated with 'kept' (bool) and 'discard_reason' (str|null). "
        "Decision B is applied here: candidates failing either threshold are marked kept=false."
    )


@register_function(config_type=RunAF2MultiBatchConfig)
async def run_af2_multimer_batch_fn(config: RunAF2MultiBatchConfig, builder: Builder):
    from modal_jobs.scoring_job import score_candidates_batch

    async def _fn(input_json: str) -> str:
        payload = json.loads(input_json)
        candidates: list[dict] = payload["candidates"]
        pdockq_threshold: float = payload.get("pdockq_threshold", 0.23)
        plddt_threshold: float  = payload.get("plddt_threshold", 70.0)

        scored = score_candidates_batch(candidates)

        kept_count = 0
        discarded_count = 0
        for c in scored:
            reasons = []
            if c["pdockq"] < pdockq_threshold:
                reasons.append(f"pdockq={c['pdockq']:.3f}<{pdockq_threshold}")
            if c["mean_interface_plddt"] < plddt_threshold:
                reasons.append(f"plddt={c['mean_interface_plddt']:.1f}<{plddt_threshold}")
            if reasons:
                c["kept"] = False
                c["discard_reason"] = "; ".join(reasons)
                discarded_count += 1
            else:
                c["kept"] = True
                c["discard_reason"] = None
                kept_count += 1

        logger.info(
            "DECISION_B: kept %d candidates, discarded %d "
            "(pdockq_threshold=%.2f, plddt_threshold=%.1f)",
            kept_count, discarded_count, pdockq_threshold, plddt_threshold,
        )
        return json.dumps(scored)

    yield FunctionInfo.from_fn(_fn, description=config.description)


# ---------------------------------------------------------------------------
# Tool 6: query_literature
# ---------------------------------------------------------------------------

class QueryLiteratureConfig(FunctionBaseConfig, name="query_literature"):
    n_results: int = 5
    description: str = (
        "Search the local PubMed Chroma index for abstracts relevant to a target. "
        "Input: input_json (str) — JSON with 'target' (str) and 'query_text' (str). "
        "Returns JSON list of {pmid, title, abstract, distance} dicts."
    )


@register_function(config_type=QueryLiteratureConfig)
async def query_literature_fn(config: QueryLiteratureConfig, builder: Builder):
    from rag.query import query_abstracts

    async def _fn(input_json: str) -> str:
        payload = json.loads(input_json)
        results = query_abstracts(
            target=payload["target"],
            query_text=payload["query_text"],
            n_results=config.n_results,
        )
        logger.info(
            "query_literature: %d abstracts for %s",
            len(results), payload["target"],
        )
        return json.dumps(results)

    yield FunctionInfo.from_fn(_fn, description=config.description)


# ---------------------------------------------------------------------------
# Tool 7: generate_report
# ---------------------------------------------------------------------------

class GenerateReportConfig(FunctionBaseConfig, name="generate_report"):
    description: str = (
        "Render the final structured markdown research report. "
        "Input: input_json (str) — JSON with keys: "
        "  'target': str, "
        "  'scored_candidates': list (from run_af2_multimer_batch), "
        "  'literature': list (from query_literature), "
        "  'decision_log': str (all DECISION_A and DECISION_B log lines). "
        "Returns a complete markdown report string ready to save as a file."
    )


@register_function(config_type=GenerateReportConfig)
async def generate_report_fn(config: GenerateReportConfig, builder: Builder):

    async def _fn(input_json: str) -> str:
        payload = json.loads(input_json)
        target: str = payload["target"]
        scored: list[dict] = payload["scored_candidates"]
        literature: list[dict] = payload.get("literature", [])
        decision_log: str = payload.get("decision_log", "(no log entries)")

        kept      = [c for c in scored if c.get("kept")]
        discarded = [c for c in scored if not c.get("kept")]

        lit_section = "\n".join(
            f"- **PMID {a['pmid']}**: {a['title']}\n  {a['abstract'][:300]}..."
            for a in literature[:5]
        )

        kept_section = "\n\n".join(
            f"### {c['candidate_id']}\n"
            f"- pDockQ: **{c['pdockq']:.3f}**\n"
            f"- Mean interface pLDDT: {c['mean_interface_plddt']:.1f}\n"
            f"- Interface contacts: {c['n_interface_contacts']}"
            for c in kept
        )

        discarded_rows = "\n".join(
            f"| {c['candidate_id']} | {c['pdockq']:.3f} | {c['discard_reason']} |"
            for c in discarded
        )

        report = f"""# Drug Discovery Report — {target}

## Decision Log

```
{decision_log}
```

## Top Binder Candidates ({len(kept)} kept)

{kept_section if kept else "_No candidates passed both thresholds._"}

## Discarded Candidates ({len(discarded)})

| Candidate | pDockQ | Reason |
|-----------|--------|--------|
{discarded_rows if discarded else "_None discarded._"}

## Literature Context

{lit_section if lit_section else "_No abstracts retrieved. Run `rag/ingest.py --target {target}` first._"}
"""
        logger.info("generate_report: report generated for %s (%d chars)", target, len(report))
        return report

    yield FunctionInfo.from_fn(_fn, description=config.description)
```

- [ ] **Step 4.2: Run full test suite — confirm all 8 tests still pass**

```bash
python -m pytest tests/ -v
```

Expected: 8 passed (3 scoring + 5 scoring_job). workflow.py is not unit-tested — the NAT ReAct orchestration layer is tested via `nat run` integration.

- [ ] **Step 4.3: Commit workflow, rag/query.py, and config together**

```bash
git add agent/workflow.py rag/query.py config/workflow.yaml
git commit -m "feat: add NAT workflow tools and YAML config for full binder design pipeline"
```

---

## Task 5: `documents/state.md` — state tracker

**Files:**
- Create: `documents/state.md`

- [ ] **Step 5.1: Write `documents/state.md`**

```markdown
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
| `modal_jobs/scoring_job.py` | TBD | Modal T4, _score_single helper, .map() batch, sort desc |
| `tests/test_scoring_job.py` | TBD | Mock NIM + Modal.map, sequence order, sort verified |
| `rag/query.py` | TBD | Chroma query interface for literature retrieval |
| `config/workflow.yaml` | TBD | NAT react_agent, nim_llm=llama-3.3-70b, 7 tools, system prompt |
| `agent/workflow.py` | TBD | 7 @register_function tools with DECISION_A/B logging |

## Not Yet Built

| File | Description |
|------|-------------|
| `app.py` | CLI entry point: `python app.py --target EGFR` |
| `validate/egfr_run.py` | EGFR end-to-end validation |
| `validate/pcsk9_run.py` | PCSK9 end-to-end validation |
| `report/template.md` | Output report template |
| Modal Image config | `modal_jobs/scoring_job.py` needs `modal.Image` with pip deps for remote execution |

## Known Constraints

| Constraint | Detail |
|------------|--------|
| **RFdiffusion retry** | Retry payload MUST differ from original — nim_cache keys on SHA-256 of payload; identical inputs return cached result silently. Widen contigs by 20 residues per retry. |
| **pDockQ threshold** | > 0.23 = keep; < 0.23 = discard (Bryant et al. 2022 standard) |
| **pLDDT threshold** | > 70.0 = confident; < 70.0 = retry (backbone) or discard (complex) |
| **Credit budget** | ~17 NIM calls per fresh run; 0 on cache hits |
| **nat module** | v1.6.0 — `aiq` alias fully removed; use `nat.*` imports everywhere |
| **AF2-Multimer response** | Assumes `result["pdbs"][0]` is the PDB string; verify against live NIM response on first run |
```

- [ ] **Step 5.2: Commit state.md**

```bash
git add documents/state.md
git commit -m "docs: add implementation state tracker after workflow completion"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `@app.function(gpu="T4")` — scoring_job.py:L23
- [x] Accept list of candidate dicts with binder_sequence, target_sequence, candidate_id — `score_candidates_batch` signature
- [x] `.map()` parallelism — `score_candidate.map(candidates)` in `score_candidates_batch`
- [x] Each invocation: AF2-Multimer NIM → PDB → `score_complex()` → result dict — `_score_single`
- [x] Result keys: candidate_id, pdockq (pLDDT), n_interface_contacts, pdb — all 5 keys present
- [x] NIM cache used — `af2_multimer_predict` routes through `nim_cache` via `nim_tools.py`
- [x] Sorted by pDockQ descending — `sorted(..., reverse=True)` in `score_candidates_batch`
- [x] One test: mock NIM, two candidates, .map() fires once with full list, results sorted — `TestScoreCandidatesBatch`
- [x] No real Modal or NIM calls in tests — all patched with `unittest.mock`
- [x] 7 NAT tool functions — fetch_sequence, run_alphafold2, run_rfdiffusion, run_proteinmpnn, run_af2_multimer_batch, query_literature, generate_report
- [x] ReAct agent Decision A — system prompt + DECISION_A logger in run_rfdiffusion_fn
- [x] ReAct agent Decision B — applied inside run_af2_multimer_batch_fn + DECISION_B logger
- [x] Load from config/workflow.yaml — YAML created with all 7 function declarations
- [x] All NIM calls through nim_tools.py — verified; workflow.py imports only from nim_tools/scoring_job/rag
- [x] Decision points logged — `logger.info("DECISION_A: ...")` and `logger.info("DECISION_B: ...")`
- [x] Decision log visible in report — generate_report tool embeds `decision_log` in output markdown
- [x] Separate commits for scoring_job and workflow — Steps 1.7 and 4.3
- [x] `documents/state.md` updated after both — Task 5

**Type consistency:**
- `score_candidates_batch(candidates: list[dict]) -> list[dict]` — used consistently in scoring_job.py and imported in workflow.py Tool 5 ✓
- Result keys from `_score_single`: `candidate_id, pdockq, mean_interface_plddt, n_interface_contacts, pdb` — matched in test assertions and Tool 5's `kept`/`discard_reason` annotation ✓
- `af2_multimer_predict(sequences=[target, binder])` — matches nim_tools.py signature ✓
- `FunctionInfo.from_fn(_fn, description=...)` — used identically in all 7 tools ✓
- `FunctionBaseConfig, name="..."` — all 7 config classes follow same pattern ✓
- `nat` imports (not `aiq`) — confirmed correct for v1.6.0 ✓
