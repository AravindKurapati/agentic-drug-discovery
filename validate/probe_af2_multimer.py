"""Probe af2_multimer_predict against the live NVIDIA endpoint.

Runnable two ways:
    python -m validate.probe_af2_multimer        # from repo root
    python validate/probe_af2_multimer.py        # also from repo root

Clears the cached result for the test payload so the live path runs.
Exit 0 = got a PDB back.
Exit 1 = endpoint is down or errored.
"""
import hashlib
import json
import os
import pathlib
import sys

# Ensure repo root is on sys.path regardless of how the script is invoked
_repo_root = pathlib.Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from dotenv import load_dotenv

load_dotenv()

# Remove cached entry for the test payload so we actually hit the network
SEQUENCES = ["MTEYKLVVVG", "ACDEFGHIKL"]
payload = {"sequences": SEQUENCES}
key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
cache_file = pathlib.Path(".nim_cache") / "af2_multimer_predict" / f"{key}.json"
if cache_file.exists():
    cache_file.unlink()
    print(f"Cleared cached entry: {cache_file}")

from agent.tools.nim_tools import af2_multimer_predict  # noqa: E402

print(f"Calling af2_multimer_predict with sequences: {SEQUENCES}")
try:
    result = af2_multimer_predict(SEQUENCES)
    backend = result.get("backend", "unknown")
    pdb_len = len(result.get("pdbs", [""])[0])
    print(f"\nOK: Got PDB ({pdb_len} chars) via backend={backend}")
    sys.exit(0)
except Exception as e:
    msg = str(e)
    if "504" in msg or "503" in msg or "timed out" in msg.lower():
        print(f"\nKNOWN UNAVAILABLE: AF2-Multimer free-tier endpoint returned {msg[:80]}")
        print("Pipeline will use MPNN log-prob proxy scoring instead.")
    else:
        print(f"\nFAIL: {e}")
    sys.exit(1)
