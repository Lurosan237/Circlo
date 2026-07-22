import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_health_check():
    """Test the health check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Health check returns HEALTH_OK or HEALTH_DEGRADED based on DB status
        assert data["code"] in ["HEALTH_OK", "HEALTH_DEGRADED"]
        assert "data" in data
        assert "status" in data["data"]


@pytest.mark.anyio
async def test_api_v1_health():
    """Test the API v1 health check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "API_HEALTH_OK"


@pytest.mark.anyio
async def test_liveness_check():
    """Test the liveness check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/live")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["code"] == "ALIVE"


@pytest.mark.anyio
async def test_security_headers():
    """Test that security headers are present in responses."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
        
        # Check security headers are present
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        
        assert "X-XSS-Protection" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "Referrer-Policy" in response.headers
