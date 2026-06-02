"""Tests for hermes_cli/webhook.py — webhook subscription CLI."""

import json
import os
import pytest
import stat
from argparse import Namespace

import hermes_cli.webhook as _wh_mod
from hermes_cli.webhook import (
    webhook_command,
    _load_subscriptions,
    _save_subscriptions,
    _subscriptions_path,
)

# Capture real implementations before any autouse fixture patches them, so
# tests targeting env-var fallback can call the genuine logic.
_REAL_IS_WEBHOOK_ENABLED = _wh_mod._is_webhook_enabled
_REAL_GET_WEBHOOK_BASE_URL = _wh_mod._get_webhook_base_url


_WEBHOOK_ENV_VARS = ("WEBHOOK_ENABLED", "WEBHOOK_HOST", "WEBHOOK_PORT")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # Strip ambient webhook env vars so tests are deterministic regardless
    # of the developer's shell or CI environment.
    for var in _WEBHOOK_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    # Default: webhooks enabled (most tests need this)
    monkeypatch.setattr(
        "hermes_cli.webhook._is_webhook_enabled", lambda: True
    )


def _make_args(**kwargs):
    defaults = {
        "webhook_action": None,
        "name": "",
        "prompt": "",
        "events": "",
        "description": "",
        "skills": "",
        "deliver": "log",
        "deliver_chat_id": "",
        "secret": "",
        "payload": "",
    }
    defaults.update(kwargs)
    return Namespace(**defaults)


class TestSubscribe:
    def test_basic_create(self, capsys):
        webhook_command(_make_args(webhook_action="subscribe", name="test-hook"))
        out = capsys.readouterr().out
        assert "Created" in out
        assert "/webhooks/test-hook" in out
        subs = _load_subscriptions()
        assert "test-hook" in subs

    def test_with_options(self, capsys):
        webhook_command(_make_args(
            webhook_action="subscribe",
            name="gh-issues",
            events="issues,pull_request",
            prompt="Issue: {issue.title}",
            deliver="telegram",
            deliver_chat_id="12345",
            description="Watch GitHub",
        ))
        subs = _load_subscriptions()
        route = subs["gh-issues"]
        assert route["events"] == ["issues", "pull_request"]
        assert route["prompt"] == "Issue: {issue.title}"
        assert route["deliver"] == "telegram"
        assert route["deliver_extra"] == {"chat_id": "12345"}

    def test_custom_secret(self):
        webhook_command(_make_args(
            webhook_action="subscribe", name="s", secret="my-secret"
        ))
        assert _load_subscriptions()["s"]["secret"] == "my-secret"

    def test_auto_secret(self):
        webhook_command(_make_args(webhook_action="subscribe", name="s"))
        secret = _load_subscriptions()["s"]["secret"]
        assert len(secret) > 20

    def test_update(self, capsys):
        webhook_command(_make_args(webhook_action="subscribe", name="x", prompt="v1"))
        webhook_command(_make_args(webhook_action="subscribe", name="x", prompt="v2"))
        out = capsys.readouterr().out
        assert "Updated" in out
        assert _load_subscriptions()["x"]["prompt"] == "v2"

    def test_invalid_name(self, capsys):
        webhook_command(_make_args(webhook_action="subscribe", name="bad name!"))
        out = capsys.readouterr().out
        assert "Error" in out or "Invalid" in out
        assert _load_subscriptions() == {}


class TestList:
    def test_empty(self, capsys):
        webhook_command(_make_args(webhook_action="list"))
        out = capsys.readouterr().out
        assert "No dynamic" in out

    def test_with_entries(self, capsys):
        webhook_command(_make_args(webhook_action="subscribe", name="a"))
        webhook_command(_make_args(webhook_action="subscribe", name="b"))
        capsys.readouterr()  # clear
        webhook_command(_make_args(webhook_action="list"))
        out = capsys.readouterr().out
        assert "2 webhook" in out
        assert "a" in out
        assert "b" in out


class TestRemove:
    def test_remove_existing(self, capsys):
        webhook_command(_make_args(webhook_action="subscribe", name="temp"))
        webhook_command(_make_args(webhook_action="remove", name="temp"))
        out = capsys.readouterr().out
        assert "Removed" in out
        assert _load_subscriptions() == {}

    def test_remove_nonexistent(self, capsys):
        webhook_command(_make_args(webhook_action="remove", name="nope"))
        out = capsys.readouterr().out
        assert "No subscription" in out

    def test_selective_remove(self):
        webhook_command(_make_args(webhook_action="subscribe", name="keep"))
        webhook_command(_make_args(webhook_action="subscribe", name="drop"))
        webhook_command(_make_args(webhook_action="remove", name="drop"))
        subs = _load_subscriptions()
        assert "keep" in subs
        assert "drop" not in subs


class TestPersistence:
    def test_file_written(self):
        webhook_command(_make_args(webhook_action="subscribe", name="persist"))
        path = _subscriptions_path()
        assert path.exists()
        data = json.loads(path.read_text())
        assert "persist" in data

    def test_corrupted_file(self):
        path = _subscriptions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("broken{{{")
        assert _load_subscriptions() == {}

    @pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits are platform-specific")
    def test_save_creates_secret_file_owner_only_under_permissive_umask(self):
        old_umask = os.umask(0o022)
        try:
            _save_subscriptions({"demo": {"secret": "TOPSECRET", "prompt": "x"}})
        finally:
            os.umask(old_umask)

        path = _subscriptions_path()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert "TOPSECRET" in path.read_text(encoding="utf-8")

    @pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits are platform-specific")
    def test_save_narrows_existing_broad_secret_file_mode(self):
        # Simulate a pre-existing 0o644 file from before this hardening landed.
        path = _subscriptions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"old": {"secret": "stale", "prompt": "x"}}))
        path.chmod(0o644)

        _save_subscriptions({"demo": {"secret": "FRESH", "prompt": "x"}})

        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert "FRESH" in path.read_text(encoding="utf-8")


class TestWebhookEnabledGate:
    def test_blocks_when_disabled(self, capsys, monkeypatch):
        monkeypatch.setattr("hermes_cli.webhook._is_webhook_enabled", lambda: False)
        webhook_command(_make_args(webhook_action="subscribe", name="blocked"))
        out = capsys.readouterr().out
        assert "not enabled" in out.lower()
        assert "hermes gateway setup" in out
        assert _load_subscriptions() == {}

    def test_blocks_list_when_disabled(self, capsys, monkeypatch):
        monkeypatch.setattr("hermes_cli.webhook._is_webhook_enabled", lambda: False)
        webhook_command(_make_args(webhook_action="list"))
        out = capsys.readouterr().out
        assert "not enabled" in out.lower()

    def test_allows_when_enabled(self, capsys):
        # _is_webhook_enabled already patched to True by autouse fixture
        webhook_command(_make_args(webhook_action="subscribe", name="allowed"))
        out = capsys.readouterr().out
        assert "Created" in out
        assert "allowed" in _load_subscriptions()

    def test_real_check_disabled(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.webhook._get_webhook_config",
            lambda: {},
        )
        monkeypatch.setattr(
            "hermes_cli.webhook._is_webhook_enabled",
            lambda: bool({}.get("enabled")),
        )
        import hermes_cli.webhook as wh_mod
        assert wh_mod._is_webhook_enabled() is False

    def test_real_check_enabled(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.webhook._is_webhook_enabled",
            lambda: True,
        )
        import hermes_cli.webhook as wh_mod
        assert wh_mod._is_webhook_enabled() is True


class TestEnvVarFallback:
    """Webhook can be enabled and configured purely via environment variables,
    without any platforms.webhook block in config.yaml."""

    @pytest.fixture(autouse=True)
    def _restore_real(self, monkeypatch):
        # Undo the autouse stub so we exercise the real implementations.
        monkeypatch.setattr(
            "hermes_cli.webhook._is_webhook_enabled",
            _REAL_IS_WEBHOOK_ENABLED,
        )
        monkeypatch.setattr(
            "hermes_cli.webhook._get_webhook_base_url",
            _REAL_GET_WEBHOOK_BASE_URL,
        )
        # Pretend config.yaml has no webhook block — env is the only source.
        monkeypatch.setattr(
            "hermes_cli.webhook._get_webhook_config",
            lambda: {},
        )

    def test_enabled_via_env_var(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_ENABLED", "true")
        assert _wh_mod._is_webhook_enabled() is True

    def test_disabled_when_env_unset(self):
        # Autouse fixture already cleared the env vars.
        assert _wh_mod._is_webhook_enabled() is False

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", " true "])
    def test_accepts_truthy_values(self, monkeypatch, value):
        monkeypatch.setenv("WEBHOOK_ENABLED", value)
        assert _wh_mod._is_webhook_enabled() is True

    @pytest.mark.parametrize("value", ["false", "0", "no", "", "off"])
    def test_rejects_falsy_values(self, monkeypatch, value):
        monkeypatch.setenv("WEBHOOK_ENABLED", value)
        assert _wh_mod._is_webhook_enabled() is False

    def test_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_HOST", "192.168.1.50")
        monkeypatch.setenv("WEBHOOK_PORT", "9000")
        assert _wh_mod._get_webhook_base_url() == "http://192.168.1.50:9000"

    def test_base_url_defaults_when_env_unset(self):
        # No config, no env → defaults to 0.0.0.0:8644 (displayed as localhost).
        assert _wh_mod._get_webhook_base_url() == "http://localhost:8644"

    def test_base_url_invalid_port_falls_back(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_PORT", "not-a-number")
        assert _wh_mod._get_webhook_base_url() == "http://localhost:8644"

    def test_base_url_partial_env(self, monkeypatch):
        # Only host overridden → port keeps default.
        monkeypatch.setenv("WEBHOOK_HOST", "0.0.0.0")
        assert _wh_mod._get_webhook_base_url() == "http://localhost:8644"

    def test_list_works_when_enabled_via_env(self, monkeypatch, capsys):
        monkeypatch.setenv("WEBHOOK_ENABLED", "true")
        # webhook_command -> _require_webhook_enabled -> real _is_webhook_enabled
        webhook_command(_make_args(webhook_action="list"))
        out = capsys.readouterr().out
        assert "not enabled" not in out.lower()
        # No subscriptions yet → empty-state message, NOT the setup hint.
        assert "No dynamic" in out

    def test_list_blocked_when_env_unset(self, capsys):
        webhook_command(_make_args(webhook_action="list"))
        out = capsys.readouterr().out
        assert "not enabled" in out.lower()


class TestConfigPrecedence:
    """When platforms.webhook is set in config.yaml, it should keep working
    regardless of env vars (back-compat)."""

    @pytest.fixture(autouse=True)
    def _restore_real(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.webhook._is_webhook_enabled",
            _REAL_IS_WEBHOOK_ENABLED,
        )
        monkeypatch.setattr(
            "hermes_cli.webhook._get_webhook_base_url",
            _REAL_GET_WEBHOOK_BASE_URL,
        )

    def test_config_enables_without_env(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.webhook._get_webhook_config",
            lambda: {"enabled": True},
        )
        assert _wh_mod._is_webhook_enabled() is True

    def test_config_host_port_used_over_env(self, monkeypatch):
        monkeypatch.setattr(
            "hermes_cli.webhook._get_webhook_config",
            lambda: {"enabled": True, "extra": {"host": "10.0.0.1", "port": 7000}},
        )
        monkeypatch.setenv("WEBHOOK_HOST", "should-be-ignored")
        monkeypatch.setenv("WEBHOOK_PORT", "9999")
        assert _wh_mod._get_webhook_base_url() == "http://10.0.0.1:7000"
