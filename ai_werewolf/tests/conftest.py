import pytest
from fastapi.testclient import TestClient

from ai_werewolf.main import create_app


@pytest.fixture
def client():
    """Create a fresh test client."""
    with TestClient(create_app()) as test_client:
        yield test_client
