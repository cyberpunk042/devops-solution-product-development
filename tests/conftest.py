"""Shared test fixtures for DSPD."""

import pytest


@pytest.fixture
def plane_url():
    """Plane instance URL for integration tests."""
    return "http://localhost:8080"


@pytest.fixture
def workspace_slug():
    """Default workspace slug."""
    return "fleet"