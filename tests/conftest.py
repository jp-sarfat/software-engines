"""
Shared pytest fixtures.
"""

import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "")

from main import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)
