#!/usr/bin/env python3
"""Fail-closed auto-launch policy for delegated child agents.

This module is intentionally pure and side-effect free.  It captures the
Warp-derived safety pattern: a model-emitted multi-agent request may only launch
automatically when it matches an approved config in the active conversation/task
scope.  Callers can keep the gate disabled while conversation-scoped persistence
is being built, then enable it via config without changing the decision logic.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Iterable, Optional

Decision = Dict[str, Any]

_ALLOWED_AUTO_LAUNCH_SCOPES = {"conversation", "task"}

# Conservative toolset-to-capability mapping used only by the delegation gate.
# If a new toolset is side-effectful, add it here before allowing it via config.
_NETWORK_TOOLSETS = {
    "browser",
    "cronjob",
    "discord",
    "discord_admin",
    "email",
    "feishu_doc",
    "feishu_drive",
    "github",
    "homeassistant",
    "image_gen",
    "kanban",
    "mcp",
    "search",
    "spotify",
    "telegram",
    "tts",
    "web",
    "webhook",
    "yuanbao",
}
_WRITE_TOOLSETS = {
    "discord",
    "discord_admin",
    "email",
    "feishu_doc",
    "feishu_drive",
    "file",
    "github",
    "homeassistant",
    "kanban",
    "mcp",
    "terminal",
    "telegram",
    "webhook",
    "yuanbao",
}
_EXTERNAL_SIDE_EFFECT_TOOLSETS = _NETWORK_TOOLSETS | _WRITE_TOOLSETS
_COMPUTER_USE_TOOLSETS = {"browser"}


def _deny(reason: str, *, effective: Optional[Dict[str, Any]] = None) -> Decision:
    return {"allowed": False, "reason": reason, "effective_values": effective or {}}


def _allow(reason: str, *, effective: Dict[str, Any]) -> Decision:
    return {"allowed": True, "reason": reason, "effective_values": effective}


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError("approval expiry must be an ISO timestamp string")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("approval expiry must include timezone information")
    return parsed


def _execution_kind(obj: Dict[str, Any]) -> Optional[str]:
    mode = obj.get("execution_mode")
    if isinstance(mode, str):
        return mode
    if isinstance(mode, dict):
        return mode.get("kind")
    return None


def _remote_field(obj: Dict[str, Any], field: str) -> str:
    mode = obj.get("execution_mode")
    if not isinstance(mode, dict):
        return ""
    value = mode.get(field)
    return value if isinstance(value, str) else ""


def _as_set(values: Any) -> set[str]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, dict)):
        return set()
    return {str(v) for v in values if v is not None}


def _capabilities_for_toolsets(toolsets: Iterable[str]) -> Dict[str, bool]:
    requested = {str(t) for t in toolsets if t}
    return {
        "network_allowed": bool(requested & _NETWORK_TOOLSETS),
        "write_allowed": bool(requested & _WRITE_TOOLSETS),
        "external_side_effects_allowed": bool(requested & _EXTERNAL_SIDE_EFFECT_TOOLSETS),
        "computer_use_enabled": bool(requested & _COMPUTER_USE_TOOLSETS),
    }


def _capabilities_for_resolved_tools(tool_names: Iterable[str]) -> Dict[str, bool]:
    names = {str(t) for t in tool_names if t}
    network = any(
        name.startswith(("web_", "browser_"))
        or name in {"image_generate", "cronjob", "send_message", "text_to_speech"}
        or name.startswith(("ha_", "kanban_"))
        for name in names
    )
    write = bool(
        names
        & {
            "terminal",
            "process",
            "write_file",
            "patch",
            "skill_manage",
            "cronjob",
            "send_message",
            "image_generate",
            "text_to_speech",
        }
    ) or any(name.startswith(("ha_", "kanban_")) for name in names)
    computer_use = any(name.startswith("browser_") for name in names)
    return {
        "network_allowed": network,
        "write_allowed": write,
        "external_side_effects_allowed": network or write,
        "computer_use_enabled": computer_use,
    }


def _check_safety_limits(request: Dict[str, Any], config: Dict[str, Any]) -> Optional[str]:
    limits = config.get("safety_limits") or {}

    child_count = len(request.get("agent_run_configs") or [])
    max_children = limits.get("max_child_agents")
    if isinstance(max_children, int) and child_count > max_children:
        return "max_child_agents_exceeded"

    timeout = request.get("timeout_sec")
    max_timeout = limits.get("max_timeout_sec")
    if isinstance(timeout, (int, float)) and isinstance(max_timeout, (int, float)):
        if timeout > max_timeout:
            return "max_timeout_exceeded"

    bool_checks = [
        ("network_allowed", "network_escalation"),
        ("write_allowed", "write_escalation"),
        ("external_side_effects_allowed", "external_side_effect_escalation"),
        ("computer_use_enabled", "computer_use_escalation"),
    ]
    for request_key, reason in bool_checks:
        config_key = "computer_use_allowed" if request_key == "computer_use_enabled" else request_key
        if request.get(request_key) is True and limits.get(config_key) is not True:
            return reason

    requested_tools = _as_set(request.get("tools"))
    allowed_tools = _as_set(limits.get("allowed_tools"))
    if requested_tools and (not allowed_tools or not requested_tools <= allowed_tools):
        return "tool_scope_escalation"

    requested_skills = _as_set(request.get("skills"))
    allowed_skills = _as_set(limits.get("allowed_skills"))
    if requested_skills and (not allowed_skills or not requested_skills <= allowed_skills):
        return "skill_scope_escalation"

    return None


def decide_auto_launch(request: Dict[str, Any], config: Optional[Dict[str, Any]]) -> Decision:
    """Return whether a child-agent request may auto-launch.

    Empty request fields inherit from the approved config, but only after the
    config is approved and scoped to the current conversation/task.
    """
    if not config:
        return _deny("no_config")

    if config.get("status") != "approved":
        return _deny("config_not_approved")

    scope_type = config.get("scope_type")
    if scope_type not in _ALLOWED_AUTO_LAUNCH_SCOPES:
        return _deny("config_not_conversation_scoped")

    request_scope = request.get("task_id") if scope_type == "task" else request.get("conversation_id")
    if not request_scope or request_scope != config.get("scope_id"):
        return _deny(
            "scope_mismatch",
            effective={"request_scope": request_scope, "config_scope": config.get("scope_id")},
        )

    raw_approval = config.get("approval", {})
    if not isinstance(raw_approval, dict):
        return _deny("invalid_approval_expiry")
    approval = raw_approval
    try:
        expires_at = _parse_time(approval.get("expires_at"))
    except (TypeError, ValueError):
        return _deny("invalid_approval_expiry")
    if expires_at and datetime.now(UTC) > expires_at:
        return _deny("config_expired")

    effective_model = request.get("model_id") or config.get("model_id")
    if effective_model != config.get("model_id"):
        return _deny(
            "model_mismatch",
            effective={"request_model_id": effective_model, "config_model_id": config.get("model_id")},
        )

    effective_harness = request.get("harness_type") or config.get("harness_type")
    if effective_harness != config.get("harness_type"):
        return _deny(
            "harness_mismatch",
            effective={
                "request_harness_type": effective_harness,
                "config_harness_type": config.get("harness_type"),
            },
        )

    request_kind = _execution_kind(request) or _execution_kind(config)
    config_kind = _execution_kind(config)
    if request_kind != config_kind:
        return _deny(
            "execution_mode_mismatch",
            effective={"request_execution_mode": request_kind, "config_execution_mode": config_kind},
        )

    effective: Dict[str, Any] = {
        "request_id": request.get("id") or request.get("request_id"),
        "conversation_id": request.get("conversation_id"),
        "task_id": request.get("task_id"),
        "config_id": config.get("config_id"),
        "scope_type": config.get("scope_type"),
        "scope_id": config.get("scope_id"),
        "model_id": effective_model,
        "harness_type": effective_harness,
        "execution_mode": request_kind,
    }

    if config_kind == "remote":
        request_env = _remote_field(request, "environment_id") or _remote_field(config, "environment_id")
        config_env = _remote_field(config, "environment_id")
        request_host = _remote_field(request, "worker_host") or _remote_field(config, "worker_host")
        config_host = _remote_field(config, "worker_host")
        effective.update({"environment_id": request_env, "worker_host": request_host})
        if request_env != config_env:
            return _deny("remote_environment_mismatch", effective=effective)
        if request_host != config_host:
            return _deny("remote_worker_host_mismatch", effective=effective)

    safety_reason = _check_safety_limits(request, config)
    if safety_reason:
        return _deny(safety_reason, effective=effective)

    return _allow("matches_approved_conversation_config", effective=effective)


def build_delegate_auto_launch_request(
    *,
    conversation_id: Optional[str],
    model_id: Optional[str],
    harness_type: str,
    task_count: int,
    timeout_sec: Optional[float],
    task_id: Optional[str] = None,
    tools: Optional[Iterable[str]] = None,
    tool_names: Optional[Iterable[str]] = None,
    skills: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Build a RunAgentsRequest-like envelope for Hermes delegate_task."""
    requested_toolsets = sorted(set(str(t) for t in (tools or []) if t))
    resolved_tool_names = sorted(set(str(t) for t in (tool_names or []) if t))
    capability_flags = (
        _capabilities_for_resolved_tools(resolved_tool_names)
        if resolved_tool_names
        else _capabilities_for_toolsets(requested_toolsets)
    )
    return {
        "conversation_id": conversation_id or "",
        "task_id": task_id or "",
        "model_id": model_id or "",
        "harness_type": harness_type,
        "execution_mode": {"kind": "local"},
        "agent_run_configs": [{} for _ in range(max(0, int(task_count)))],
        "timeout_sec": timeout_sec,
        **capability_flags,
        "tools": requested_toolsets,
        "resolved_tools": resolved_tool_names,
        "skills": sorted(set(str(s) for s in (skills or []) if s)),
    }
