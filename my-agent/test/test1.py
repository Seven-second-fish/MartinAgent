"""第 2 课练习：验证 parse_react_response 判定顺序。

推荐在 my-agent/ 下运行：
  cd ~/project/MartinAgent/my-agent
  source agent-env/bin/activate
  python test/test1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把 my-agent/ 加入搜索路径（本文件在 test/ 里，上一级才是含 src 的目录）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.react_parser import parse_react_response

samples = [
'''Thought: 要查时间
Action: get_time
Action Input: （无参数）''',

'''Thought: 完成了
Final Answer: 现在是下午三点''',

'''Action: get_time''',

'''你好呀！''',
]

for i, s in enumerate(samples, 1):
    print(i, parse_react_response(s))
