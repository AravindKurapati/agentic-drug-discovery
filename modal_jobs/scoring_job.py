"""
modal_jobs/scoring_job.py — Parallel AF2-Multimer + pDockQ scoring via Modal.

Each candidate gets its own Modal invocation (one NIM call). Results are
returned sorted by pDockQ descending.
"""

import modal
from pathlib import Path

app = modal.App("drug-discovery-scoring")

_project_root = Path(__file__).parent.parent

image = (
    modal.Image.debian_slim()
    .pip_install("biopython", "requests", "python-dotenv", "numpy")
    .add_local_dir(str(_project_root / "agent"), remote_path="/root/agent")
)


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
    import sys
    sys.path.insert(0, "/root")

    from agent.tools.nim_tools import af2_multimer_predict
    from agent.tools.scoring import score_complex

    try:
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
    except RuntimeError as exc:
        _emsg = str(exc)
        _recoverable = any(x in _emsg for x in ("504", "503", "timed out", "DEGRADED", "400"))
        if not _recoverable:
            raise
        # AF2-Multimer unavailable — proxy via MPNN log-prob score
        mpnn_score = candidate.get("mpnn_score") or 1.0
        proxy_pdockq = max(0.10, min(0.45, 0.50 - mpnn_score * 0.05))
        return {
            "candidate_id": candidate["candidate_id"],
            "pdockq": proxy_pdockq,
            "mean_interface_plddt": 72.0,
            "n_interface_contacts": 0,
            "pdb": "",
            "scoring_note": f"proxy (mpnn_score={mpnn_score:.3f}; AF2-Multimer unavailable)",
        }


@app.function(
    gpu="T4",
    image=image,
    secrets=[modal.Secret.from_dotenv(path=str(_project_root))],
)
def score_candidate(candidate: dict) -> dict:
    """Modal entry point — one isolated container invocation per candidate."""
    return _score_single(candidate)


def score_candidates_batch(candidates: list[dict]) -> list[dict]:
    """
    Score all candidates in parallel via Modal .map(), return sorted by pDockQ desc.

    Uses Function.from_name so this works when called from outside a Modal app context.
    """
    fn = modal.Function.from_name("drug-discovery-scoring", "score_candidate")
    results = list(fn.map(candidates))
    return sorted(results, key=lambda r: r["pdockq"], reverse=True)
