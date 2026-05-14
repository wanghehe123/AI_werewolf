import pytest
from fastapi.testclient import TestClient

from ai_werewolf.main import app
from ai_werewolf.api.admin import auth_router


@pytest.fixture
def client():
    """Create a test client with admin routes included."""
    # Include admin router in the app for testing
    app.include_router(auth_router)
    with TestClient(app) as test_client:
        yield test_client