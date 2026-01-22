from unittest.mock import MagicMock, patch

import pytest
from datacommons_mcp.middleware import APIKeyMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


async def homepage(request):  # noqa: ARG001
    return JSONResponse({"status": "ok"})


@pytest.fixture
def client():
    # Define a simple Starlette app with the middleware
    middleware = [Middleware(APIKeyMiddleware)]
    routes = [Route("/", homepage)]
    app = Starlette(routes=routes, middleware=middleware)
    return TestClient(app)


def test_api_key_header_present(client):
    """Verify use_api_key is called when X-API-Key header is present."""
    with patch("datacommons_mcp.middleware.use_api_key") as mock_use_api_key:
        # Configuration for the mock context manager
        mock_context_manager = MagicMock()
        mock_use_api_key.return_value.__enter__.return_value = mock_context_manager

        headers = {"X-API-Key": "test-key-123"}
        response = client.get("/", headers=headers)

        assert response.status_code == 200
        mock_use_api_key.assert_called_once_with("test-key-123")
        # Ensure the context manager was actually entered
        mock_use_api_key.return_value.__enter__.assert_called_once()
        mock_use_api_key.return_value.__exit__.assert_called_once()


def test_api_key_header_missing(client):
    """Verify use_api_key is NOT called when X-API-Key header is missing."""
    with patch("datacommons_mcp.middleware.use_api_key") as mock_use_api_key:
        response = client.get("/")

        assert response.status_code == 200
        mock_use_api_key.assert_not_called()


def test_api_key_header_empty(client):
    """Verify use_api_key is NOT called when X-API-Key header is empty."""
    with patch("datacommons_mcp.middleware.use_api_key") as mock_use_api_key:
        headers = {"X-API-Key": ""}
        response = client.get("/", headers=headers)

        assert response.status_code == 200
        mock_use_api_key.assert_not_called()
