from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import Brand, ToolInvocation
from src.store import audit_store


@pytest.fixture(autouse=True)
def clear_store() -> None:
    audit_store.clear()


def make_invocation(
    *,
    brand: Brand = "efood",
    tool_name: str = "search_prs",
    called_at: datetime | None = None,
) -> ToolInvocation:
    return ToolInvocation(
        tool_call_id=uuid4(),
        caller_brand=brand,
        tool_name=tool_name,
        args={"brand": brand},
        outcome="success",
        result_summary="1 result",
        latency_ms=12,
        called_at=called_at or datetime.now(timezone.utc),
    )


def test_audit_empty() -> None:
    client = TestClient(app)

    response = client.get("/audit")

    assert response.status_code == 200
    assert response.json() == []


def test_audit_filters_by_brand() -> None:
    client = TestClient(app)
    audit_store.add(make_invocation(brand="efood"))
    audit_store.add(make_invocation(brand="glovo"))

    response = client.get("/audit", params={"brand": "glovo"})

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["caller_brand"] == "glovo"


def test_audit_applies_limit() -> None:
    client = TestClient(app)
    audit_store.add(make_invocation(tool_name="search_prs"))
    audit_store.add(make_invocation(tool_name="get_slack_messages"))
    audit_store.add(make_invocation(tool_name="fetch_gdrive_doc"))

    response = client.get("/audit", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_audit_returns_most_recent_first() -> None:
    client = TestClient(app)
    audit_store.add(
        make_invocation(
            tool_name="older",
            called_at=datetime(2026, 5, 10, 1, 0, tzinfo=timezone.utc),
        )
    )
    audit_store.add(
        make_invocation(
            tool_name="newer",
            called_at=datetime(2026, 5, 10, 2, 0, tzinfo=timezone.utc),
        )
    )

    response = client.get("/audit")

    assert response.status_code == 200
    records = response.json()
    assert [record["tool_name"] for record in records] == ["newer", "older"]
