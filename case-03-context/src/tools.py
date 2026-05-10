"""Tool catalog and deterministic mock executions."""

from datetime import UTC, datetime
from typing import Any

from src.mock_data import MOCK_DOCS, MOCK_PRS, MOCK_SLACK
from src.models import (
    FetchGdriveDocArgs,
    GetSlackMessagesArgs,
    SearchPrsArgs,
    ToolDefinition,
)


def list_tools() -> list[ToolDefinition]:
    """Return tool catalog definitions."""
    return [
        ToolDefinition(
            name="search_prs",
            description="Search mock pull requests by target brand and query.",
            args_schema=SearchPrsArgs.model_json_schema(),
            brand_requirements="Caller brand must equal the requested brand.",
        ),
        ToolDefinition(
            name="get_slack_messages",
            description="Read recent messages from an allowed mock Slack channel.",
            args_schema=GetSlackMessagesArgs.model_json_schema(),
            brand_requirements="Caller brand can only read channels in its whitelist.",
        ),
        ToolDefinition(
            name="fetch_gdrive_doc",
            description="Fetch a mock Google Drive document by document id.",
            args_schema=FetchGdriveDocArgs.model_json_schema(),
            brand_requirements="Caller brand must match the document's brand.",
        ),
    ]


def search_prs(args: SearchPrsArgs) -> tuple[list[dict[str, Any]], str]:
    """Search PRs for the requested brand."""
    query = args.query.casefold()
    prs = [
        pr
        for pr in MOCK_PRS
        if pr["brand"] == args.brand and query in pr["title"].casefold()
    ][: args.limit]
    return prs, f"{len(prs)} PRs returned for {args.brand}"


def get_slack_messages(args: GetSlackMessagesArgs) -> tuple[list[dict[str, Any]], str]:
    """Return recent messages from one mock Slack channel."""
    channel = MOCK_SLACK.get(args.channel, {"messages": []})
    messages = [
        message
        for message in channel["messages"]
        if datetime.fromisoformat(message["ts"]) >= with_utc(args.since)
    ]
    return messages, f"{len(messages)} Slack messages returned from {args.channel}"


def fetch_gdrive_doc(args: FetchGdriveDocArgs) -> tuple[dict[str, Any], str]:
    """Return one mock Google Drive document."""
    doc = MOCK_DOCS[args.doc_id]
    result = {
        "doc_id": args.doc_id,
        "title": doc["title"],
        "content": doc["content"],
        "brand": doc["brand"],
        "last_modified": doc["last_modified"],
    }
    return result, f"document returned: {doc['title']}"


def with_utc(value: datetime) -> datetime:
    """Treat timezone-free ISO 8601 inputs as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
