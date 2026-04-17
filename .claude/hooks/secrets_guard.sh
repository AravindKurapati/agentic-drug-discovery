#!/bin/bash
# Block commands that would expose .env or *.txt API key file contents.
input=$(cat)
cmd=$(echo "$input" | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
if echo "$cmd" | grep -qiE '(cat|type|head|tail|less|more|echo|print)\s+.*\.(env|txt)'; then
  python -c "import json; print(json.dumps({'continue': False, 'stopReason': 'BLOCKED: Refusing to expose .env or *.txt key file contents. Access secrets only via os.environ in code.'}))"
  exit 0
fi
exit 0
