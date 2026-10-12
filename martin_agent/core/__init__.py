"""
core 包对外 API。

内部模块（llm_client / prompts）由不同 agent 使用，不必从这里导出。

可选依赖解耦：LangGraphAgent 依赖第三方框架（langchain-core / langgraph）。
这里用 PEP 562 的模块级 __getattr__ 做惰性导入——只装核心依赖时，导入本包
不会连带加载模式 5，其余四种模式与 pytest 都能正常使用。
"""

from martin_agent.core.react_agent import ReActAgent
from martin_agent.core.plan_solve_agent import PlanAndSolveAgent
from martin_agent.core.reflection_agent import ReflectionAgent
from martin_agent.core.autogen_agent import AutoGenAgent

__all__ = [
    "ReActAgent",
    "PlanAndSolveAgent",
    "ReflectionAgent",
    "AutoGenAgent",
    "LangGraphAgent",
]

# 依赖可选框架的属性：属性名 → 提供它的模块（键即该模块内的类名）
_LAZY_MODULES = {"LangGraphAgent": "martin_agent.core.langgraph_agent"}

_INSTALL_HINT = (
    "模式 5（LangGraph）需要可选依赖 langchain-core / langgraph。\n"
    '  安装：pip install -e ".[langgraph]"\n'
    "  或：  pip install langchain-core langgraph"
)


def __getattr__(name: str):
    """PEP 562：访问时才导入依赖可选框架的属性，缺依赖时给出安装提示。"""
    module_name = _LAZY_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(f"{exc}\n{_INSTALL_HINT}") from exc

    value = getattr(module, name)
    globals()[name] = value  # 缓存，后续访问不再走 __getattr__
    return value


def __dir__() -> list[str]:
    """让 dir() 与编辑器补全能看到惰性属性。"""
    return sorted(set(globals()) | set(__all__))
