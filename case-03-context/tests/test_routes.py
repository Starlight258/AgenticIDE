"""Route-level regression tests for tool invocation behavior."""

from fastapi.testclient import TestClient

from src.main import app
from src.store import audit_store


def test_health_returns_ok() -> None:
    """Health endpoint remains available."""
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tools_catalog_uses_args_schema() -> None:
    """Catalog exposes schemas generated from the args models."""
    client = TestClient(app)

    response = client.get("/tools")

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()}
    assert tools["search_prs"]["args_schema"]["title"] == "SearchPrsArgs"
    assert tools["fetch_gdrive_doc"]["args_schema"]["title"] == "FetchGdriveDocArgs"


def test_denied_pr_search_is_audited() -> None:
    """Cross-brand PR search is denied and recorded."""
    audit_store.clear()
    client = TestClient(app)

    response = client.post(
        "/tools/search_prs/invoke",
        headers={"X-Caller-Brand": "efood"},
        json={"brand": "glovo", "query": "ETA"},
    )
    audit_response = client.get("/audit")

    assert response.status_code == 403
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["outcome"] == "brand_denied"


def test_gdrive_permission_uses_doc_metadata_brand() -> None:
    """GDrive allows caller-owned docs even when args.brand differs."""
    audit_store.clear()
    client = TestClient(app)

    response = client.post(
        "/tools/fetch_gdrive_doc/invoke",
        headers={"X-Caller-Brand": "efood"},
        json={"brand": "glovo", "doc_id": "doc-efood-checkout"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["title"] == "efood checkout rollout"
