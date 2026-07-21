#!/usr/bin/env python3
"""Tests for delegation auto-launch approved-config policy."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from tools.delegation_autolaunch_policy import (
    build_delegate_auto_launch_request,
    decide_auto_launch,
)
from tools.delegate_tool import delegate_task


def _approved_config(**overrides):
    config = {
        "config_id": "cfg-001",
        "scope_type": "conversation",
        "scope_id": "sess-123",
        "status": "approved",
        "model_id": "anthropic/claude-sonnet-4",
        "harness_type": "hermes-delegate",
        "execution_mode": {"kind": "local"},
        "approval": {"approved_by": "gabriel", "approved_at": "2026-05-03T12:00:00Z"},
        "safety_limits": {
            "max_child_agents": 2,
            "max_timeout_sec": 600,
            "network_allowed": True,
            "write_allowed": False,
            "external_side_effects_allowed": True,
            "computer_use_allowed": False,
            "allowed_tools": ["web", "terminal"],
            "allowed_skills": [],
        },
    }
    config.update(overrides)
    return config


def _request(**overrides):
    request = build_delegate_auto_launch_request(
        conversation_id="sess-123",
        model_id="anthropic/claude-sonnet-4",
        harness_type="hermes-delegate",
        task_count=1,
        timeout_sec=120,
        tools=["web"],
        skills=[],
    )
    request.update(overrides)
    return request


def _parent():
    parent = MagicMock()
    parent.session_id = "sess-123"
    parent.task_id = "legacy-task-123"
    parent._current_task_id = "task-123"
    parent.model = "anthropic/claude-sonnet-4"
    parent.provider = "anthropic"
    parent.base_url = None
    parent.api_key = "***"
    parent.api_mode = "chat_completions"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._delegate_depth = 0
    parent.enabled_toolsets = ["web"]
    return parent


class TestDelegationAutoLaunchPolicy:
    def test_no_config_denies(self):
        decision = decide_auto_launch(_request(), None)
        assert decision == {"allowed": False, "reason": "no_config", "effective_values": {}}

    def test_global_config_denies_even_when_approved(self):
        decision = decide_auto_launch(_request(), _approved_config(scope_type="global"))
        assert decision["allowed"] is False
        assert decision["reason"] == "config_not_conversation_scoped"

    def test_matching_conversation_config_allows(self):
        decision = decide_auto_launch(_request(), _approved_config())
        assert decision["allowed"] is True
        assert decision["reason"] == "matches_approved_conversation_config"
        assert decision["effective_values"]["model_id"] == "anthropic/claude-sonnet-4"

    def test_empty_request_fields_inherit_after_approval(self):
        decision = decide_auto_launch(_request(model_id="", harness_type=""), _approved_config())
        assert decision["allowed"] is True
        assert decision["effective_values"]["harness_type"] == "hermes-delegate"

    def test_model_mismatch_denies(self):
        decision = decide_auto_launch(_request(model_id="other-model"), _approved_config())
        assert decision["allowed"] is False
        assert decision["reason"] == "model_mismatch"

    def test_safety_escalation_denies(self):
        decision = decide_auto_launch(_request(write_allowed=True), _approved_config())
        assert decision["allowed"] is False
        assert decision["reason"] == "write_escalation"

    def test_missing_allowed_tools_deny_when_tools_requested(self):
        config = _approved_config(safety_limits={
            "max_child_agents": 2,
            "max_timeout_sec": 600,
            "network_allowed": True,
            "external_side_effects_allowed": True,
        })
        decision = decide_auto_launch(_request(), config)
        assert decision["allowed"] is False
        assert decision["reason"] == "tool_scope_escalation"

    def test_invalid_approval_expiry_denies_instead_of_raising(self):
        config = _approved_config(approval={"expires_at": "not-a-date"})
        decision = decide_auto_launch(_request(), config)
        assert decision["allowed"] is False
        assert decision["reason"] == "invalid_approval_expiry"

    def test_non_dict_approval_denies_instead_of_raising(self):
        for malformed in ("malformed", [], 0, False):
            config = _approved_config(approval=malformed)
            decision = decide_auto_launch(_request(), config)
            assert decision["allowed"] is False
            assert decision["reason"] == "invalid_approval_expiry"

    def test_resolved_tool_names_drive_capability_flags(self):
        request = build_delegate_auto_launch_request(
            conversation_id="sess-123",
            model_id="anthropic/claude-sonnet-4",
            harness_type="hermes-delegate",
            task_count=1,
            timeout_sec=120,
            tools=["debugging"],
            tool_names=["terminal", "write_file", "web_search"],
        )
        decision = decide_auto_launch(
            request,
            _approved_config(safety_limits={
                "max_child_agents": 2,
                "max_timeout_sec": 600,
                "network_allowed": False,
                "write_allowed": False,
                "external_side_effects_allowed": False,
                "allowed_tools": ["debugging"],
            }),
        )
        assert decision["allowed"] is False
        assert decision["reason"] in {"network_escalation", "write_escalation", "external_side_effect_escalation"}

    def test_task_scoped_config_uses_task_id_not_conversation_id(self):
        decision = decide_auto_launch(
            _request(task_id="task-123"),
            _approved_config(scope_type="task", scope_id="task-123"),
        )
        assert decision["allowed"] is True

    def test_task_scoped_config_without_task_id_denies(self):
        decision = decide_auto_launch(
            _request(),
            _approved_config(scope_type="task", scope_id="task-123"),
        )
        assert decision["allowed"] is False
        assert decision["reason"] == "scope_mismatch"

    def test_delegate_task_gate_denies_before_child_build_without_config(self):
        cfg = {
            "require_approved_config_for_auto_launch": True,
            "max_iterations": 1,
            "child_timeout_seconds": 120,
        }
        creds = {
            "model": "anthropic/claude-sonnet-4",
            "provider": None,
            "base_url": None,
            "api_key": None,
            "api_mode": None,
            "command": None,
            "args": None,
        }
        with patch("tools.delegate_tool._load_config", return_value=cfg), \
             patch("tools.delegate_tool._resolve_delegation_credentials", return_value=creds), \
             patch("tools.delegate_tool._build_child_agent") as build_child:
            payload = json.loads(delegate_task(goal="Research safely", parent_agent=_parent()))

        assert "error" in payload
        assert "no_config" in payload["error"]
        build_child.assert_not_called()

    def test_delegate_task_gate_accepts_current_task_scoped_config(self):
        cfg = {
            "require_approved_config_for_auto_launch": True,
            "approved_config": _approved_config(scope_type="task", scope_id="task-123"),
            "max_iterations": 1,
            "child_timeout_seconds": 120,
        }
        creds = {
            "model": "anthropic/claude-sonnet-4",
            "provider": None,
            "base_url": None,
            "api_key": None,
            "api_mode": None,
            "command": None,
            "args": None,
        }
        child = MagicMock()
        with patch("tools.delegate_tool._load_config", return_value=cfg), \
             patch("tools.delegate_tool._resolve_delegation_credentials", return_value=creds), \
             patch("tools.delegate_tool._build_child_agent", return_value=child), \
             patch("tools.delegate_tool._run_single_child", return_value={"status": "completed", "summary": "ok"}) as run_child:
            payload = json.loads(delegate_task(goal="Research safely", parent_agent=_parent()))

        assert "results" in payload
        run_child.assert_called_once()
