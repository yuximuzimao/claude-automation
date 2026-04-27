#!/bin/bash
# 健身视频技能入口
# 用法：bash run.sh [import|reset|plan|status|dry-run]
# 无参数默认执行 import

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SKILL_DIR"

CMD="${1:-import}"

case "$CMD" in
  import)
    python3 batch_import.py --regen-plan
    ;;
  reset)
    rm -f .processed_hashes.json
    python3 batch_import.py --regen-plan
    ;;
  plan)
    shift
    python3 gen_plan.py "$@"
    ;;
  status)
    python3 - <<'EOF'
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
db = json.loads(Path('exercise_db.json').read_text())
exs = db['exercises']
from collections import Counter
types = Counter(e.get('type','其他') for e in exs)
print(f'动作库共 {len(exs)} 个动作')
for t, n in sorted(types.items(), key=lambda x: -x[1]):
    print(f'  {t}: {n} 个')
processed = json.loads(Path('.processed_hashes.json').read_text()) if Path('.processed_hashes.json').exists() else []
print(f'已处理视频: {len(processed)} 个')
EOF
    ;;
  dry-run)
    python3 batch_import.py --dry-run
    ;;
  *)
    echo "用法: bash run.sh [import|reset|plan|status|dry-run]"
    echo "  import    — 处理新视频并生成训练计划（默认）"
    echo "  reset     — 清空记录重新处理所有视频"
    echo "  plan      — 仅重新生成训练计划"
    echo "  status    — 查看动作库统计"
    echo "  dry-run   — 预览待处理视频"
    ;;
esac
