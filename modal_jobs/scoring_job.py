"""
modal_jobs/scoring_job.py — Parallel AF2-Multimer + pDockQ scoring via Modal.

Each candidate gets its own Modal invocation (one NIM call). Results are
returned sorted by pDockQ descending.
"""

import modal

from agent.tools.nim_tools import af2_multimer_predict
from agent.tools.scoring import score_complex

app = modal.App("drug-discovery-scoring")

image = modal.Image.debian_slim().pip_install("biopython", "requests", "python-dotenv", "numpy")


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


@app.function(gpu="T4", image=image)
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
