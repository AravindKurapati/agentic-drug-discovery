import hashlib
import json
import pathlib

CACHE_DIR = pathlib.Path(".nim_cache")


def cached_nim_call(tool_name: str, payload: dict, call_fn):
    """Wrap a NIM API call with disk caching. Cache hit = 0 API credits."""
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    cache_file = CACHE_DIR / tool_name / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    result = call_fn(payload)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result))
    return result
