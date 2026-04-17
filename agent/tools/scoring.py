"""
scoring.py — Interface pLDDT extraction and pDockQ computation for AlphaFold2-Multimer outputs.

pDockQ formula from Bryant et al. 2022 (Wallner lab):
  https://doi.org/10.1038/s41467-022-28865-w
"""

import io
import math

from Bio.PDB import PDBParser


def extract_interface_plddt(
    pdb_str: str,
    chain_a: str = "A",
    chain_b: str = "B",
    dist_threshold: float = 8.0,
) -> tuple[float, int]:
    """
    Parse a PDB string and return the mean B-factor (pLDDT proxy) of interface
    residues plus the number of inter-chain Cα contacts.

    A residue is considered an interface residue when its Cα atom is within
    `dist_threshold` Å of at least one Cα atom in the opposite chain.
    Only ATOM records are considered (HETATM residues are skipped).

    Returns
    -------
    (mean_interface_plddt, n_contacts)
        mean_interface_plddt : mean B-factor over all interface residues in
                               both chains (0.0 if no interface found).
        n_contacts           : number of (chain_a residue, chain_b residue)
                               Cα pairs within the distance threshold.
    """
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("complex", io.StringIO(pdb_str))

    # Collect {chain_id: [(ca_atom, bfactor), ...]} — skip HETATM
    chain_ca: dict[str, list[tuple]] = {}
    for model in structure:
        for chain in model:
            cid = chain.get_id()
            if cid not in (chain_a, chain_b):
                continue
            atoms = []
            for residue in chain:
                # Skip HETATM records
                if residue.get_id()[0] != " ":
                    continue
                if "CA" not in residue:
                    continue
                ca = residue["CA"]
                atoms.append((ca, ca.get_bfactor()))
            chain_ca[cid] = atoms

    if chain_a not in chain_ca or chain_b not in chain_ca:
        return (0.0, 0)

    atoms_a = chain_ca[chain_a]
    atoms_b = chain_ca[chain_b]

    if not atoms_a or not atoms_b:
        return (0.0, 0)

    # Find interface residues and count contacts
    threshold_sq = dist_threshold ** 2
    interface_a: set[int] = set()  # indices into atoms_a
    interface_b: set[int] = set()  # indices into atoms_b
    n_contacts = 0

    for i, (ca_a, _) in enumerate(atoms_a):
        for j, (ca_b, _) in enumerate(atoms_b):
            diff = ca_a.get_vector() - ca_b.get_vector()
            if diff.norm() <= dist_threshold:
                n_contacts += 1
                interface_a.add(i)
                interface_b.add(j)

    if n_contacts == 0:
        return (0.0, 0)

    bfactors = [atoms_a[i][1] for i in interface_a] + [atoms_b[j][1] for j in interface_b]
    mean_plddt = sum(bfactors) / len(bfactors)

    return (mean_plddt, n_contacts)


def compute_pdockq(mean_interface_plddt: float, n_contacts: int) -> float:
    """
    Compute pDockQ using the Wallner lab sigmoid formula (Bryant et al. 2022).

    Parameters
    ----------
    mean_interface_plddt : mean B-factor / pLDDT of interface residues.
    n_contacts           : number of inter-chain Cα contacts.

    Returns
    -------
    pDockQ score in [0.018, ~0.742], rounded to 4 decimal places.
    """
    if n_contacts == 0:
        return 0.018

    x = mean_interface_plddt * math.log(n_contacts + 1)
    pdockq = 0.724 / (1 + math.exp(-0.052 * (x - 152.611))) + 0.018

    return round(pdockq, 4)


def score_complex(
    pdb_str: str,
    binder_chain: str = "B",
    target_chain: str = "A",
) -> dict:
    """
    High-level entry point: score a two-chain complex from a PDB string.

    Parameters
    ----------
    pdb_str      : raw PDB file contents as a string.
    binder_chain : chain ID of the binder (default "B").
    target_chain : chain ID of the target (default "A").

    Returns
    -------
    dict with keys:
        pdockq               : float
        mean_interface_plddt : float
        n_interface_contacts : int
    """
    mean_plddt, n_contacts = extract_interface_plddt(
        pdb_str, chain_a=target_chain, chain_b=binder_chain
    )
    pdockq = compute_pdockq(mean_plddt, n_contacts)

    return {
        "pdockq": pdockq,
        "mean_interface_plddt": mean_plddt,
        "n_interface_contacts": n_contacts,
    }
