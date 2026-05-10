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
    assert "brand_requirements" in tools["search_prs"]
    assert "limit" in tools["search_prs"]["args_schema"]["required"]
    assert "channel" in tools["get_slack_messages"]["args_schema"]["required"]
    assert "since" in tools["get_slack_messages"]["args_schema"]["required"]


def test_openapi_shows_tool_specific_request_schemas() -> None:
    """Swagger exposes concrete schemas for each invokable tool."""
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/tools/{name}/invoke" not in paths
    schema = paths["/tools/search_prs/invoke"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert schema == {"$ref": "#/components/schemas/SearchPrsArgs"}


def test_denied_pr_search_is_audited() -> None:
    """Cross-brand PR search is denied and recorded."""
    audit_store.clear()
    client = TestClient(app)

    response = client.post(
        "/tools/search_prs/invoke",
        headers={"X-Caller-Brand": "efood"},
        json={"brand": "glovo", "query": "ETA", "limit": 5},
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
    result = response.json()["result"]
    assert result["title"] == "efood checkout rollout"
    assert result["brand"] == "efood"
    assert result["last_modified"] == "2026-05-10T01:00:00+00:00"


def test_search_prs_returns_spec_shape_and_applies_limit() -> None:
    """PR search returns assignment field names and honors limit."""
    audit_store.clear()
    client = TestClient(app)

    response = client.post(
        "/tools/search_prs/invoke",
        headers={"X-Caller-Brand": "efood"},
        json={"brand": "efood", "query": "c", "limit": 1},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert len(result) == 1
    assert set(result[0]) == {"pr_id", "title", "author", "status", "brand"}


def test_slack_messages_use_channel_since_and_spec_shape() -> None:
    """Slack tool accepts assignment args and returns assignment field names."""
    audit_store.clear()
    client = TestClient(app)

    response = client.post(
        "/tools/get_slack_messages/invoke",
        headers={"X-Caller-Brand": "efood"},
        json={
            "brand": "efood",
            "channel": "C-EFOOD-OPS",
            "since": "2026-05-10T01:30:00+00:00",
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert len(result) == 1
    assert set(result[0]) == {"ts", "author", "text", "channel", "brand"}
    assert result[0]["author"] == "joon"


def test_slack_since_accepts_timezone_free_iso8601() -> None:
    """Slack since follows the spec even without an explicit UTC offset."""
    audit_store.clear()
    client = TestClient(app)

    response = client.post(
        "/tools/get_slack_messages/invoke",
        headers={"X-Caller-Brand": "efood"},
        json={
            "brand": "efood",
            "channel": "C-EFOOD-OPS",
            "since": "2026-05-10T01:30:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["result"][0]["author"] == "joon"
