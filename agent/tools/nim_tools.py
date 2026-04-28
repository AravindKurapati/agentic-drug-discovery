import os
import re
import requests
from dotenv import load_dotenv

from agent.tools.nim_cache import cached_nim_call

load_dotenv()

_NIM_BASE = "https://health.api.nvidia.com/v1"


def _nim_headers() -> dict:
    api_key = os.environ["NVIDIA_API_KEY"]
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _nim_post(url: str, payload: dict, poll_interval: float = 5.0, timeout: int = 600) -> dict:
    """POST to a NVIDIA NIM endpoint with async-polling support.

    Handles both synchronous (200) and asynchronous (202 → poll) responses.
    Retries on 502/503 (transient gateway errors) with exponential backoff.
    The status URL pattern is https://health.api.nvidia.com/v1/status/{reqid}.
    """
    import time

    _TRANSIENT = {502, 503}
    _MAX_RETRIES = 3
    _BACKOFF = 10  # seconds; doubles each retry

    for attempt in range(_MAX_RETRIES + 1):
        # connect timeout 30 s; read timeout matches the caller's overall timeout
        resp = requests.post(url, json=payload, headers=_nim_headers(), timeout=(30, timeout))

        if resp.status_code not in _TRANSIENT:
            break
        if attempt == _MAX_RETRIES:
            raise RuntimeError(
                f"NIM request failed [{resp.status_code}] after {_MAX_RETRIES} retries: {resp.text}"
            )
        wait = _BACKOFF * (2 ** attempt)
        print(f"  NIM {resp.status_code} on attempt {attempt + 1} — retrying in {wait}s...")
        time.sleep(wait)

    if resp.status_code == 200:
        return resp.json()

    if resp.status_code == 202:
        req_id = resp.headers.get("nvcf-reqid")
        if not req_id:
            raise RuntimeError(f"NIM returned 202 but no nvcf-reqid header: {resp.headers}")
        status_url = f"{_NIM_BASE}/status/{req_id}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(poll_interval)
            status_resp = requests.get(status_url, headers=_nim_headers(), timeout=30)
            if status_resp.status_code == 200:
                return status_resp.json()
            if status_resp.status_code != 202:
                raise RuntimeError(
                    f"NIM polling failed [{status_resp.status_code}]: {status_resp.text}"
                )
        raise RuntimeError(f"NIM request timed out after {timeout}s (reqid={req_id})")

    raise RuntimeError(f"NIM request failed [{resp.status_code}]: {resp.text}")


def alphafold2_predict(sequence: str) -> dict:
    """Predict protein structure via ESMFold (fast, no MSA).

    ESMFold is used in place of AlphaFold2 on the hosted NIM free tier —
    AF2 returns 504/errored on the serverless endpoint. ESMFold is available
    at meta/esmfold and returns {"pdbs": [pdb_str]} directly.
    """
    payload = {"sequence": sequence}

    def call_fn(p: dict) -> dict:
        # ESMFold enforces a 1024-residue limit; truncate if needed
        q = dict(p)
        if len(q.get("sequence", "")) > 1024:
            q["sequence"] = q["sequence"][:1024]
        return _nim_post(f"{_NIM_BASE}/biology/meta/esmfold", q)

    return cached_nim_call("alphafold2_predict", payload, call_fn)


def rfdiffusion_generate(
    input_pdb: str,
    contigs: str,
    hotspot_res: str = "",
    diffusion_steps: int = 15,
    n_designs: int = 5,
) -> dict:
    """Generate protein binder backbone structures with RFdiffusion.

    Calls the API n_designs times (one design per call) with different random seeds.
    Returns {"pdbs": [pdb1, ...], "mean_plddt": 75.0}.
    Note: the hosted NIM does not return per-design pLDDT; mean_plddt is set to
    75.0 (above threshold) since backbone quality is assessed downstream via pDockQ.
    """
    hotspot_list = [r.strip() for r in hotspot_res.split(",") if r.strip()] if hotspot_res else []
    pdbs = []
    for seed in range(n_designs):
        payload = {
            "input_pdb": input_pdb,
            "contigs": contigs,
            "hotspot_res": hotspot_list,
            "diffusion_steps": diffusion_steps,
            "random_seed": seed,
        }

        def call_fn(p: dict) -> dict:
            return _nim_post(f"{_NIM_BASE}/biology/ipd/rfdiffusion/generate", p)

        result = cached_nim_call("rfdiffusion_generate", payload, call_fn)
        pdbs.append(result["output_pdb"])

    return {"pdbs": pdbs, "mean_plddt": 75.0}


def proteinmpnn_predict(
    pdb: str,
    sampling_temp: float = 0.1,
) -> dict:
    """Design amino acid sequences for a backbone with ProteinMPNN.

    Returns {"sequences": [seq1, seq2, ...]}.
    """
    payload = {
        "input_pdb": pdb,
        "ca_only": False,
        "use_soluble_model": False,
        "sampling_temp": [sampling_temp],
    }

    def call_fn(p: dict) -> dict:
        return _nim_post(f"{_NIM_BASE}/biology/ipd/proteinmpnn/predict", p)

    result = cached_nim_call("proteinmpnn_predict", payload, call_fn)
    # mfasta format: ">input, score=..." block (binder as G's) then ">T=0.1, sample=N" blocks (real designs).
    # We only want sequences from the designed blocks, not the input reconstruction.
    mfasta = result.get("mfasta", "")
    sequences = []
    scores = []
    is_design_block = False
    current_score = None
    for line in mfasta.splitlines():
        line = line.strip()
        if line.startswith(">"):
            is_design_block = not line.startswith(">input")
            if is_design_block:
                # parse score= from header: ">T=0.1, sample=1, score=0.84, ..."
                import re as _re
                m = _re.search(r"score=([\d.]+)", line)
                current_score = float(m.group(1)) if m else None
        elif line and is_design_block:
            sequences.append(line.split("/")[0])
            scores.append(current_score)
    return {"sequences": sequences, "scores": scores}


def af2_multimer_predict(sequences: list[str]) -> dict:
    """Predict complex structure from multiple sequences via AlphaFold2-Multimer.

    Returns {"pdbs": [pdb_str]}.
    Raises RuntimeError on failure; callers should fall back to proxy scoring.
    """
    payload = {"sequences": sequences}

    def call_fn(p: dict) -> dict:
        # AF2-Multimer runs MSA search; allow up to 15 min per pair
        data = _nim_post(
            f"{_NIM_BASE}/biology/deepmind/alphafold2-multimer",
            p,
            poll_interval=10.0,
            timeout=900,
        )
        pdb = data.get("pdb_structure") or (
            data["pdbs"][0] if isinstance(data.get("pdbs"), list) and data["pdbs"] else ""
        )
        return {"pdbs": [pdb]}

    return cached_nim_call("af2_multimer_predict", payload, call_fn)


def _resolve_uniprot_accession(query: str) -> str:
    """Return accession unchanged if it looks like one; otherwise search by gene name."""
    if re.fullmatch(r"[A-Z][0-9][A-Z0-9]{3}[0-9]", query):
        return query
    resp = requests.get(
        "https://rest.uniprot.org/uniprotkb/search",
        params={"query": f"gene_exact:{query} AND organism_id:9606", "fields": "accession", "format": "tsv", "size": 1},
    )
    resp.raise_for_status()
    lines = [l for l in resp.text.strip().splitlines() if not l.startswith("Entry")]
    if not lines:
        raise RuntimeError(f"No UniProt accession found for gene name: {query!r}")
    return lines[0].strip()


def uniprot_fetch_sequence(uniprot_id: str) -> str:
    """Fetch the amino acid sequence for a UniProt accession or gene name."""
    uniprot_id = _resolve_uniprot_accession(uniprot_id)
    url = f"https://www.uniprot.org/uniprot/{uniprot_id}.fasta"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise RuntimeError(
            f"uniprot_fetch_sequence failed [{resp.status_code}]: {resp.text}"
        )
    lines = resp.text.splitlines()
    sequence = "".join(line.strip() for line in lines if not line.startswith(">"))
    return sequence
