#!/bin/bash
# Warn before commands that may call live NIM APIs and spend free-tier credits.
input=$(cat)
cmd=$(echo "$input" | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
if echo "$cmd" | grep -qiE '(app\.py|health\.api\.nvidia|rfdiffusion|proteinmpnn|alphafold2|modal run|modal deploy)'; then
  python -c "import json; print(json.dumps({'systemMessage': 'NIM CACHE CHECK: This command may call live NIM APIs (free-tier credits). Confirm nim_cache.py is active -- cache hits cost \$0.'}))"
fi
exit 0
