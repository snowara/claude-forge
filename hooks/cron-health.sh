#!/bin/bash
# cron-health.sh - SessionStart Hook
# patrol 결과에 실패가 있으면 한줄 요약 표시
# exit 0 필수

INPUT=$(cat)

MSG=$(echo "$INPUT" | python3 -c "
import sys, json, os
from datetime import datetime, timedelta

try:
    d = json.load(sys.stdin)
except:
    sys.exit(0)

results_dir = os.path.expanduser('~/.claude/patrol/results')
if not os.path.isdir(results_dir):
    sys.exit(0)

# today first, fallback to yesterday
today = datetime.now().strftime('%Y-%m-%d')
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

path = None
date_label = None
for dt in [today, yesterday]:
    p = os.path.join(results_dir, f'{dt}.json')
    if os.path.exists(p):
        path = p
        date_label = dt
        break

if not path:
    sys.exit(0)

try:
    with open(path, 'r') as f:
        data = json.load(f)
except:
    sys.exit(0)

results = data if isinstance(data, list) else data.get('results', [])
if not results:
    sys.exit(0)

# check if any non-pass/skip
has_failure = False
for r in results:
    status = r.get('status', '').lower()
    if status not in ('pass', 'skip'):
        has_failure = True
        break

if not has_failure:
    sys.exit(0)

# build summary
name_map = {
    'blog-writer': 'blog-writer',
    'daangn-biz': 'daangn',
    'product-finder': 'finder',
    'session': 'session',
}
parts = []
for r in results:
    name = r.get('target', r.get('name', 'unknown'))
    short = name_map.get(name, name)
    status = r.get('status', 'unknown').upper()
    parts.append(f'{short} {status}')

print(f'[PATROL {date_label}] {\" | \".join(parts)}')
" 2>/dev/null)

if [[ -n "$MSG" ]]; then
    echo "$MSG" >&2
fi

exit 0
