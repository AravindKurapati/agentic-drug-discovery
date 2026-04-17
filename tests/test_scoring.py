"""
Tests for agent/tools/scoring.py

Test 1: Synthetic two-chain PDB — formula unit test (no network)
Test 2: Real RCSB structure smoke test (1ZHH, chains I & J)
Test 3: Edge case — single-chain PDB, no partner chain present
"""

import math
import urllib.request

import pytest

from agent.tools.scoring import (
    compute_pdockq,
    extract_interface_plddt,
    score_complex,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_atom_line(
    serial: int,
    name: str,
    res_name: str,
    chain: str,
    res_seq: int,
    x: float,
    y: float,
    z: float,
    bfactor: float,
    element: str = "C",
) -> str:
    """Return a single PDB ATOM record as a fixed-width string."""
    return (
        f"ATOM  {serial:5d}  {name:<3s} {res_name:3s} {chain:1s}{res_seq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00{bfactor:6.2f}           {element:>2s}  "
    )


def _build_synthetic_pdb() -> str:
    """
    Two-chain PDB (A and B), each with 3 ALA residues.

    Chain A Cα positions: (0,0,0), (3,0,0), (6,0,0)
    Chain B Cα positions: (0,5,0), (3,5,0), (6,5,0)

    All 9 inter-chain Cα distances are within 8 Å (max diagonal = 7.81 Å).
    All B-factors = 85.0.
    """
    lines = []
    serial = 1

    # Chain A — 3 residues
    for i, (x, y, z) in enumerate([(0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (6.0, 0.0, 0.0)], start=1):
        lines.append(_make_atom_line(serial, "CA", "ALA", "A", i, x, y, z, 85.0))
        serial += 1

    # Chain B — 3 residues
    for i, (x, y, z) in enumerate([(0.0, 5.0, 0.0), (3.0, 5.0, 0.0), (6.0, 5.0, 0.0)], start=1):
        lines.append(_make_atom_line(serial, "CA", "ALA", "B", i, x, y, z, 85.0))
        serial += 1

    lines.append("END")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test 1 — formula unit test (no network)
# ---------------------------------------------------------------------------

def test_synthetic_pdockq():
    """All 9 Cα pairs are within 8 Å; mean B-factor = 85.0; pDockQ must match formula."""
    pdb_str = _build_synthetic_pdb()

    mean_plddt, n_contacts = extract_interface_plddt(pdb_str, chain_a="A", chain_b="B")

    assert n_contacts == 9, f"Expected 9 contacts, got {n_contacts}"
    assert abs(mean_plddt - 85.0) < 1e-6, f"Expected mean pLDDT 85.0, got {mean_plddt}"

    # Manually computed expected pDockQ
    x_expected = 85.0 * math.log(9 + 1)
    pdockq_expected = round(
        0.724 / (1 + math.exp(-0.052 * (x_expected - 152.611))) + 0.018, 4
    )

    pdockq = compute_pdockq(mean_plddt, n_contacts)
    assert abs(pdockq - pdockq_expected) < 0.001, (
        f"pDockQ {pdockq} differs from expected {pdockq_expected} by more than 0.001"
    )


# ---------------------------------------------------------------------------
# Test 2 — real RCSB structure smoke test
# ---------------------------------------------------------------------------

def test_real_structure_1zhh():
    """
    Fetch 1ZHH from RCSB; validate geometry (n_contacts > 0) and formula range.
    B-factors are crystallographic — only geometry and range are tested.
    1ZHH contains chains A (heavy/light antibody) and B (antigen).
    """
    url = "https://files.rcsb.org/download/1ZHH.pdb"
    pdb_str = urllib.request.urlopen(url, timeout=30).read().decode()

    mean_plddt, n_contacts = extract_interface_plddt(pdb_str, chain_a="A", chain_b="B")

    assert n_contacts > 0, "Expected a real interface in 1ZHH chains I/J"
    assert 0.0 <= mean_plddt <= 100.0, (
        f"mean_plddt={mean_plddt} is outside the valid B-factor range [0, 100]"
    )

    pdockq = compute_pdockq(mean_plddt, n_contacts)
    assert 0.018 <= pdockq <= 0.75, (
        f"pDockQ={pdockq} is outside the expected range [0.018, 0.75]"
    )


# ---------------------------------------------------------------------------
# Test 3 — edge case: missing partner chain
# ---------------------------------------------------------------------------

def test_single_chain_edge_case():
    """score_complex on a single-chain PDB should return zero-contact defaults."""
    single_chain_pdb = "\n".join([
        "ATOM      1  CA  ALA A   1       1.000   1.000   1.000  1.00 50.00           C  ",
        "ATOM      2  CA  ALA A   2       5.000   1.000   1.000  1.00 50.00           C  ",
        "END",
    ])

    result = score_complex(single_chain_pdb, binder_chain="B", target_chain="A")

    assert result["pdockq"] == 0.018, (
        f"Expected pdockq=0.018 for missing chain, got {result['pdockq']}"
    )
    assert result["n_interface_contacts"] == 0, (
        f"Expected 0 contacts for missing chain, got {result['n_interface_contacts']}"
    )
