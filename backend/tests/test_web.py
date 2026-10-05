"""Production entry point: API under /api, the built frontend (SPA) everywhere else."""
import pytest
from fastapi.testclient import TestClient

from app import web as web_module


@pytest.fixture
def site(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>app</title>")
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    (tmp_path / "robots.txt").write_text("User-agent: *")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    import importlib

    module = importlib.reload(web_module)
    yield TestClient(module.web)
    monkeypatch.delenv("FRONTEND_DIST")
    importlib.reload(web_module)


def test_spa_routes_assets_and_api(site):
    for path in ("/", "/login", "/painel/produtos", "/../../etc/passwd"):
        response = site.get(path)
        assert response.status_code == 200 and "<title>app</title>" in response.text
        assert response.headers["cache-control"] == "no-cache"
    assert site.get("/robots.txt").text == "User-agent: *"
    asset = site.get("/assets/app-123.js")
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    missing = site.get("/assets/old-999.js")
    assert missing.status_code == 404 and "immutable" not in missing.headers.get("cache-control", "")
    assert site.get("/api/platform/plans").json()["plans"]
    assert site.get("/health").json() == {"status": "ok"}
