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

{lit_section if lit_section else f"_No abstracts retrieved. Run `rag/ingest.py --target {target}` first._"}
"""
        logger.info("generate_report: report generated for %s (%d chars)", target, len(report))
        return report

    yield FunctionInfo.from_fn(_fn, description=config.description)
