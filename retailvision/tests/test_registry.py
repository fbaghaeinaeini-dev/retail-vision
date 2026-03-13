"""Tests for the tool registry."""

from agent.models import ToolResult
from agent.tools.registry import ToolRegistry


class TestToolRegistry:
    """Tool registry tests."""

    def test_register_and_get(self):
        @ToolRegistry.register("_test_tool")
        def _test_tool(state, config):
            return ToolResult(success=True, message="test")

        assert ToolRegistry.has("_test_tool")
        fn = ToolRegistry.get("_test_tool")
        assert fn is _test_tool

    def test_list_tools(self):
        tools = ToolRegistry.list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_execute(self, empty_state, config):
        @ToolRegistry.register("_test_execute")
        def _test_execute(state, config):
            return ToolResult(success=True, data={"value": 42}, message="ok")

        result = ToolRegistry.execute("_test_execute", empty_state, config)
        assert result.success
        assert result.data["value"] == 42

    def test_get_missing_tool_raises(self):
        import pytest
        with pytest.raises(KeyError, match="not registered"):
            ToolRegistry.get("_nonexistent_tool_xyz")

    def test_all_pipeline_tools_registered(self):
        """Verify all pipeline tools are registered."""
        # Import orchestrator to trigger all tool registrations
        import agent.orchestrator  # noqa: F401
        from agent.orchestrator import PHASE1_TOOLS, PHASE4_TOOLS, PHASE5_TOOLS, PHASE6_TOOLS
        from agent.strategy_profiles import get_profile

        # Check fixed-phase tools
        for tool_name in PHASE1_TOOLS + PHASE4_TOOLS + PHASE5_TOOLS + PHASE6_TOOLS:
            assert ToolRegistry.has(tool_name), f"Tool '{tool_name}' not registered"

        # Check all tools referenced in strategy profiles
        profile = get_profile("general")
        for tool_name in profile["phase2_tools"] + profile["phase3_tools"]:
            assert ToolRegistry.has(tool_name), f"Tool '{tool_name}' not registered"

        # Check quick analytics tool
        assert ToolRegistry.has("compute_quick_zone_analytics")
