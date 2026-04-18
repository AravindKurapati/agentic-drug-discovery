import hashlib
import json
import os
import pathlib

CACHE_DIR = pathlib.Path(".nim_cache")


class CacheMissError(Exception):
    """Raised in dry-run mode when a NIM result is not in the local cache."""
    def __init__(self, tool_name: str, input_hash: str):
        self.tool_name = tool_name
        self.input_hash = input_hash
        super().__init__(
            f"Cache miss in dry-run: tool={tool_name} hash={input_hash[:12]}... "
            "Run without --dry-run to populate cache."
        )


def cached_nim_call(tool_name: str, payload: dict, call_fn):
    """Wrap a NIM API call with disk caching. Cache hit = 0 API credits."""
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    cache_file = CACHE_DIR / tool_name / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    if os.environ.get("NIM_DRY_RUN"):
        raise CacheMissError(tool_name, key)
    result = call_fn(payload)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result))
    return result
