"""In-memory mock backend records."""

from typing import Any

from src.models import Brand

MOCK_PRS: list[dict[str, Any]] = [
    {
        "brand": "efood",
        "id": 101,
        "title": "Tighten checkout context permissions",
        "author": "mina",
        "state": "open",
    },
    {
        "brand": "efood",
        "id": 102,
        "title": "Fix restaurant menu cache",
        "author": "joon",
        "state": "merged",
    },
    {
        "brand": "glovo",
        "id": 201,
        "title": "Add courier ETA guardrail",
        "author": "sofia",
        "state": "open",
    },
    {
        "brand": "talabat",
        "id": 301,
        "title": "Refine payment retry telemetry",
        "author": "omar",
        "state": "open",
    },
]

MOCK_SLACK: dict[str, dict[str, Any]] = {
    "C-EFOOD-OPS": {
        "brand": "efood",
        "messages": [
            {"user": "mina", "text": "Checkout rollout is ready for review."},
            {"user": "joon", "text": "Menu cache fix is live in staging."},
        ],
    },
    "C-GLOVO-OPS": {
        "brand": "glovo",
        "messages": [
            {"user": "sofia", "text": "Courier ETA alerts need one more check."},
            {"user": "leo", "text": "Dispatch latency dashboard was updated."},
        ],
    },
    "C-TALABAT-OPS": {
        "brand": "talabat",
        "messages": [
            {"user": "omar", "text": "Payment retries are below threshold."},
            {"user": "layla", "text": "Fraud review notes are in the doc."},
        ],
    },
}

MOCK_DOCS: dict[str, dict[str, Any]] = {
    "doc-efood-checkout": {
        "brand": "efood",
        "title": "efood checkout rollout",
        "content": "Checkout rollout notes with partner-specific risks.",
    },
    "doc-glovo-courier": {
        "brand": "glovo",
        "title": "glovo courier ETA plan",
        "content": "Courier ETA plan with dispatch and alerting details.",
    },
    "doc-talabat-payments": {
        "brand": "talabat",
        "title": "talabat payment retry review",
        "content": "Payment retry review with incident follow-up notes.",
    },
}

SLACK_CHANNEL_WHITELIST: dict[Brand, set[str]] = {
    "efood": {"C-EFOOD-OPS"},
    "glovo": {"C-GLOVO-OPS"},
    "talabat": {"C-TALABAT-OPS"},
}
