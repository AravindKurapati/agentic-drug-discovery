import os
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


def alphafold2_predict(sequence: str) -> dict:
    """Predict protein structure from a single amino acid sequence via AlphaFold2."""
    payload = {"sequence": sequence}

    def call_fn(p: dict) -> dict:
        url = f"{_NIM_BASE}/protein-structure/alphafold2/predict-structure-from-sequence"
        resp = requests.post(url, json=p, headers=_nim_headers())
        if resp.status_code != 200:
            raise RuntimeError(
                f"alphafold2_predict failed [{resp.status_code}]: {resp.text}"
            )
        return resp.json()

    return cached_nim_call("alphafold2_predict", payload, call_fn)


def rfdiffusion_generate(
    input_pdb: str,
    contigs: str,
    hotspot_res: str = "",
    diffusion_steps: int = 15,
) -> dict:
    """Generate protein binder backbones with RFDiffusion."""
    payload = {
        "input_pdb": input_pdb,
        "contigs": contigs,
        "hotspot_res": hotspot_res,
        "diffusion_steps": diffusion_steps,
    }

    def call_fn(p: dict) -> dict:
        url = f"{_NIM_BASE}/biology/ipd/rfdiffusion/generate"
        resp = requests.post(url, json=p, headers=_nim_headers())
        if resp.status_code != 200:
            raise RuntimeError(
                f"rfdiffusion_generate failed [{resp.status_code}]: {resp.text}"
            )
        return resp.json()

    return cached_nim_call("rfdiffusion_generate", payload, call_fn)


def proteinmpnn_predict(
    pdb: str,
    model: str = "v_48_020",
    sampling_temperature: float = 0.1,
) -> dict:
    """Design sequences for a given backbone with ProteinMPNN."""
    payload = {
        "pdb_string": pdb,
        "model": model,
        "sampling_temperature": sampling_temperature,
    }

    def call_fn(p: dict) -> dict:
        url = f"{_NIM_BASE}/biology/ipd/proteinmpnn/predict"
        resp = requests.post(url, json=p, headers=_nim_headers())
        if resp.status_code != 200:
            raise RuntimeError(
                f"proteinmpnn_predict failed [{resp.status_code}]: {resp.text}"
            )
        return resp.json()

    return cached_nim_call("proteinmpnn_predict", payload, call_fn)


def af2_multimer_predict(sequences: list[str]) -> dict:
    """Predict complex structure from multiple sequences via AlphaFold2-Multimer."""
    payload = {
        "sequences": sequences,
        "databases": ["uniref90", "mgnify", "small_bfd"],
    }

    def call_fn(p: dict) -> dict:
        url = f"{_NIM_BASE}/protein-structure/alphafold2/multimer/predict-structure-from-sequences"
        resp = requests.post(url, json=p, headers=_nim_headers())
        if resp.status_code != 200:
            raise RuntimeError(
                f"af2_multimer_predict failed [{resp.status_code}]: {resp.text}"
            )
        return resp.json()

    return cached_nim_call("af2_multimer_predict", payload, call_fn)


def uniprot_fetch_sequence(uniprot_id: str) -> str:
    """Fetch the amino acid sequence for a UniProt accession (no API key required)."""
    url = f"https://www.uniprot.org/uniprot/{uniprot_id}.fasta"
    resp = requests.get(url)
    if resp.status_code != 200:
        raise RuntimeError(
            f"uniprot_fetch_sequence failed [{resp.status_code}]: {resp.text}"
        )
    lines = resp.text.splitlines()
    # Strip all FASTA header lines (lines starting with '>')
    sequence = "".join(line.strip() for line in lines if not line.startswith(">"))
    return sequence
