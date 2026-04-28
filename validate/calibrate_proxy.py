"""
calibrate_proxy.py — Validate the pDockQ proxy formula against known binder complexes.

Downloads real PDB structures of EGFR and PCSK9 complexes from RCSB, counts
interface contacts, and shows what pDockQ would be at typical AF2 pLDDT levels.
Compares those values to the proxy formula used when AF2-Multimer is unavailable.

Real PDB structures store crystallographic B-factors (not pLDDT) so we can't
compute pDockQ directly. Instead we:
  1. Count interface contacts from the real geometry (ground truth contact count)
  2. Compute pDockQ at hypothetical pLDDT = 75 and 85 (typical AF2 confident range)
  3. Print the proxy formula's output range for comparison

Usage:
    python validate/calibrate_proxy.py
"""

import io
import math
import sys

import requests

sys.path.insert(0, ".")
from agent.tools.scoring import extract_interface_plddt, compute_pdockq

RCSB_PDB_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"

KNOWN_COMPLEXES = [
    {
        "pdb_id": "1IVO",
        "description": "EGFR domain III + cetuximab Fab heavy chain (strong clinical binder)",
        "target": "EGFR",
        "chain_a": "A",
        "chain_b": "B",
    },
    {
        "pdb_id": "2P4E",
        "description": "PCSK9 + LDLR EGF-A domain (natural binding partner)",
        "target": "PCSK9",
        "chain_a": "A",
        "chain_b": "B",
    },
    {
        "pdb_id": "3BKX",
        "description": "EGFR kinase domain + lapatinib-bound (intra-domain contact reference)",
        "target": "EGFR",
        "chain_a": "A",
        "chain_b": "B",
    },
]

PROXY_MPNN_SCORES = [0.5, 0.75, 1.0, 1.25, 1.5]


def fetch_pdb(pdb_id: str) -> str:
    url = RCSB_PDB_URL.format(pdb_id=pdb_id)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def proxy_pdockq(mpnn_score: float) -> float:
    return max(0.10, min(0.45, 0.45 - (mpnn_score - 0.5) * 0.233))


def main():
    print("=" * 70)
    print("pDockQ Proxy Calibration — Known Binder Complexes")
    print("=" * 70)

    print("\n--- Real structure contact counts (geometry from RCSB PDB) ---\n")
    for entry in KNOWN_COMPLEXES:
        pdb_id = entry["pdb_id"]
        print(f"Fetching {pdb_id}: {entry['description']}")
        try:
            pdb_str = fetch_pdb(pdb_id)
        except Exception as exc:
            print(f"  ERROR fetching {pdb_id}: {exc}\n")
            continue

        _, n_contacts = extract_interface_plddt(
            pdb_str,
            chain_a=entry["chain_a"],
            chain_b=entry["chain_b"],
        )

        if n_contacts == 0:
            print(f"  WARNING: no contacts found between chains {entry['chain_a']} and {entry['chain_b']}.")
            print(f"  The PDB may have different chain IDs — check {pdb_id} on RCSB.\n")
            continue

        pdockq_75 = compute_pdockq(75.0, n_contacts)
        pdockq_85 = compute_pdockq(85.0, n_contacts)

        print(f"  Interface Ca contacts : {n_contacts}")
        print(f"  pDockQ @ pLDDT=75     : {pdockq_75:.4f}  (threshold: >0.23 = likely binder)")
        print(f"  pDockQ @ pLDDT=85     : {pdockq_85:.4f}")
        verdict = "PASS" if pdockq_75 > 0.23 else "FAIL"
        print(f"  Verdict @ pLDDT=75    : {verdict}")
        print()

    print("--- Proxy formula output range (used when AF2-Multimer unavailable) ---\n")
    print(f"  {'MPNN score':>12}  {'proxy pDockQ':>13}  {'threshold':>10}")
    print(f"  {'-'*12}  {'-'*13}  {'-'*10}")
    for ms in PROXY_MPNN_SCORES:
        pq = proxy_pdockq(ms)
        verdict = "PASS" if pq > 0.23 else "FAIL"
        print(f"  {ms:>12.2f}  {pq:>13.4f}  {verdict:>10}")

    print()
    print("Note: Real PDB B-factors != pLDDT, so contact counts are the reliable")
    print("ground truth here. pDockQ values at pLDDT=75/85 show what we'd expect")
    print("from AF2-Multimer predictions of real binders at typical confidence levels.")


if __name__ == "__main__":
    main()
