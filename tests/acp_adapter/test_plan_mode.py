"""Plan mode guard: mutating tools are refused while planning.

The guard is a ContextVar so non-ACP sessions (CLI, gateway) never see it.
These tests exercise the real helpers — no mocks — because the guard is the
only thing standing between "plan mode" and a tool that changes the machine.
"""

from __future__ import annotations

import json

import pytest

from acp_adapter.edit_approval import (
    PLAN_MODE_BLOCKED_TOOLS,
    is_plan_mode,
    maybe_block_for_plan_mode,
    reset_plan_mode,
    set_plan_mode,
)


@pytest.fixture
def plan_mode():
    """Enable plan mode for one test and always unbind it afterwards."""
    token = set_plan_mode(True)
    try:
        yield
    finally:
        reset_plan_mode(token)


def test_plan_mode_is_off_by_default():
    assert is_plan_mode() is False
    assert maybe_block_for_plan_mode("write_file") is None
    assert maybe_block_for_plan_mode("terminal") is None


@pytest.mark.parametrize("tool_name", sorted(PLAN_MODE_BLOCKED_TOOLS))
def test_plan_mode_blocks_every_mutating_tool(plan_mode, tool_name):
    blocked = maybe_block_for_plan_mode(tool_name)

    assert blocked is not None
    payload = json.loads(blocked)
    assert tool_name in payload["error"]
    assert "Plan mode" in payload["error"]


@pytest.mark.parametrize(
    "tool_name",
    ["read_file", "search_files", "web_search", "web_extract", "skill_view"],
)
def test_plan_mode_allows_read_only_tools(plan_mode, tool_name):
    assert maybe_block_for_plan_mode(tool_name) is None


def test_terminal_is_blocked_because_shell_commands_cannot_be_vetted():
    """`terminal` must stay blocked: 'rm -rf' and 'ls' are indistinguishable here."""
    assert "terminal" in PLAN_MODE_BLOCKED_TOOLS


def test_plan_mode_binding_is_restored_after_reset():
    token = set_plan_mode(True)
    assert is_plan_mode() is True
    reset_plan_mode(token)

    assert is_plan_mode() is False
    assert maybe_block_for_plan_mode("write_file") is None


def test_plan_mode_does_not_leak_into_another_context():
    """A turn in plan mode must not disarm tools for a concurrent session."""
    import contextvars

    token = set_plan_mode(True)
    try:
        # A context copied *before* the flag is read still carries it, so assert
        # the inverse: a fresh context created from the default has it off.
        result = contextvars.Context().run(lambda: is_plan_mode())
        assert result is False
    finally:
        reset_plan_mode(token)
