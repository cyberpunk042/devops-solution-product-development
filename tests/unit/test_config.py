"""Tests for dspd.config module."""

import os

import pytest


def test_settings_loads_defaults():
    """Settings should have sensible defaults even with no env vars."""
    from dspd.config import DspdSettings

    s = DspdSettings.from_env()
    assert s.PLANE_URL  # should have default
    assert s.COMPOSE_PROJECT == "dspd-plane"
    assert s.PROJECT_ROOT  # should be set


def test_settings_reads_env(monkeypatch):
    """Settings should read from environment variables."""
    from dspd.config import DspdSettings

    monkeypatch.setenv("PLANE_URL", "http://test:9999")
    monkeypatch.setenv("PLANE_API_KEY", "test-key-123")
    monkeypatch.setenv("PLANE_WORKSPACE_SLUG", "test-ws")

    s = DspdSettings.from_env()
    assert s.PLANE_URL == "http://test:9999"
    assert s.PLANE_API_KEY == "test-key-123"
    assert s.PLANE_WORKSPACE_SLUG == "test-ws"


def test_settings_ocmc_fallback(monkeypatch):
    """OCMC settings fall back to LOCAL_AUTH_TOKEN and BASE_URL."""
    from dspd.config import DspdSettings

    monkeypatch.delenv("OCMC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OCMC_BASE_URL", raising=False)
    monkeypatch.setenv("LOCAL_AUTH_TOKEN", "fallback-token")
    monkeypatch.setenv("BASE_URL", "http://fallback:8000")

    s = DspdSettings.from_env()
    assert s.OCMC_AUTH_TOKEN == "fallback-token"
    assert s.OCMC_BASE_URL == "http://fallback:8000"


def test_settings_immutable():
    """Settings should be frozen (immutable)."""
    from dspd.config import DspdSettings

    s = DspdSettings.from_env()
    with pytest.raises(AttributeError):
        s.PLANE_URL = "http://changed"


def test_settings_workspace_slug_fallback(monkeypatch):
    """PLANE_WORKSPACE is accepted as fallback for PLANE_WORKSPACE_SLUG."""
    from dspd.config import DspdSettings

    monkeypatch.delenv("PLANE_WORKSPACE_SLUG", raising=False)
    monkeypatch.setenv("PLANE_WORKSPACE", "my-workspace")

    s = DspdSettings.from_env()
    assert s.PLANE_WORKSPACE_SLUG == "my-workspace"