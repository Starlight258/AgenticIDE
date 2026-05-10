"""In-memory mock backend records."""

from typing import Any

from src.models import Brand

MOCK_PRS: list[dict[str, Any]] = [
    {
        "brand": "efood",
        "pr_id": 101,
        "title": "Tighten checkout context permissions",
        "author": "mina",
        "status": "open",
    },
    {
        "brand": "efood",
        "pr_id": 102,
        "title": "Fix restaurant menu cache",
        "author": "joon",
        "status": "merged",
    },
    {
        "brand": "glovo",
        "pr_id": 201,
        "title": "Add courier ETA guardrail",
        "author": "sofia",
        "status": "open",
    },
    {
        "brand": "talabat",
        "pr_id": 301,
        "title": "Refine payment retry telemetry",
        "author": "omar",
        "status": "open",
    },
]

MOCK_SLACK: dict[str, dict[str, Any]] = {
    "C-EFOOD-OPS": {
        "brand": "efood",
        "messages": [
            {
                "ts": "2026-05-10T01:00:00+00:00",
                "author": "mina",
                "text": "Checkout rollout is ready for review.",
                "channel": "C-EFOOD-OPS",
                "brand": "efood",
            },
            {
                "ts": "2026-05-10T02:00:00+00:00",
                "author": "joon",
                "text": "Menu cache fix is live in staging.",
                "channel": "C-EFOOD-OPS",
                "brand": "efood",
            },
        ],
    },
    "C-GLOVO-OPS": {
        "brand": "glovo",
        "messages": [
            {
                "ts": "2026-05-10T01:00:00+00:00",
                "author": "sofia",
                "text": "Courier ETA alerts need one more check.",
                "channel": "C-GLOVO-OPS",
                "brand": "glovo",
            },
            {
                "ts": "2026-05-10T02:00:00+00:00",
                "author": "leo",
                "text": "Dispatch latency dashboard was updated.",
                "channel": "C-GLOVO-OPS",
                "brand": "glovo",
            },
        ],
    },
    "C-TALABAT-OPS": {
        "brand": "talabat",
        "messages": [
            {
                "ts": "2026-05-10T01:00:00+00:00",
                "author": "omar",
                "text": "Payment retries are below threshold.",
                "channel": "C-TALABAT-OPS",
                "brand": "talabat",
            },
            {
                "ts": "2026-05-10T02:00:00+00:00",
                "author": "layla",
                "text": "Fraud review notes are in the doc.",
                "channel": "C-TALABAT-OPS",
                "brand": "talabat",
            },
        ],
    },
}

MOCK_DOCS: dict[str, dict[str, Any]] = {
    "doc-efood-checkout": {
        "brand": "efood",
        "title": "efood checkout rollout",
        "content": "Checkout rollout notes with partner-specific risks.",
        "last_modified": "2026-05-10T01:00:00+00:00",
    },
    "doc-glovo-courier": {
        "brand": "glovo",
        "title": "glovo courier ETA plan",
        "content": "Courier ETA plan with dispatch and alerting details.",
        "last_modified": "2026-05-10T01:00:00+00:00",
    },
    "doc-talabat-payments": {
        "brand": "talabat",
        "title": "talabat payment retry review",
        "content": "Payment retry review with incident follow-up notes.",
        "last_modified": "2026-05-10T01:00:00+00:00",
    },
}

SLACK_CHANNEL_WHITELIST: dict[Brand, set[str]] = {
    "efood": {"C-EFOOD-OPS"},
    "glovo": {"C-GLOVO-OPS"},
    "talabat": {"C-TALABAT-OPS"},
}
