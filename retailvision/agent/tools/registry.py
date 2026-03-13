"""Tool registry for the agent pipeline.

Each tool is a function with signature: (state, config) -> ToolResult.
Tools are registered by name and looked up during pipeline execution.
"""

from __future__ import annotations

from typing import Callable

from loguru import logger

from agent.models import ToolResult


class ToolRegistry:
    """Registry of pipeline tools keyed by name."""

    _tools: dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a tool function."""

        def decorator(func: Callable) -> Callable:
            cls._tools[name] = func
            return func

        return decorator

    @classmethod
    def get(cls, name: str) -> Callable:
        if name not in cls._tools:
            raise KeyError(f"Tool '{name}' not registered. Available: {list(cls._tools.keys())}")
        return cls._tools[name]

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls._tools

    @classmethod
    def list_tools(cls) -> list[str]:
        return list(cls._tools.keys())

    @classmethod
    def execute(cls, name: str, state, config) -> ToolResult:
        """Execute a named tool with error wrapping."""
        tool_fn = cls.get(name)
        try:
            result = tool_fn(state, config)
            if not isinstance(result, ToolResult):
                result = ToolResult(success=True, data=result, message=f"{name} completed")
            return result
        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}")
            raise
