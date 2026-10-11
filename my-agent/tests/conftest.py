"""pytest 公共配置：把 my-agent/ 加入 sys.path，使 tests/ 能 `import src.*`。

正常通过仓库根目录的 pytest.ini（pythonpath = my-agent）已经可用；
这里再兜一层，保证直接 `python -m pytest my-agent/tests` 也能跑。
"""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
