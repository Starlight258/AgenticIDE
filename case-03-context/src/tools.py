"""Tool catalog and deterministic mock executions."""

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
        ),
        ToolDefinition(
            name="get_slack_messages",
            description="Read recent messages from an allowed mock Slack channel.",
            args_schema=GetSlackMessagesArgs.model_json_schema(),
        ),
        ToolDefinition(
            name="fetch_gdrive_doc",
            description="Fetch a mock Google Drive document by document id.",
            args_schema=FetchGdriveDocArgs.model_json_schema(),
        ),
    ]


def search_prs(args: SearchPrsArgs) -> tuple[dict[str, Any], str]:
    """Search PRs for the requested brand."""
    query = args.query.casefold()
    prs = [
        pr
        for pr in MOCK_PRS
        if pr["brand"] == args.brand and query in pr["title"].casefold()
    ]
    return {"prs": prs}, f"{len(prs)} PRs returned for {args.brand}"


def get_slack_messages(args: GetSlackMessagesArgs) -> tuple[dict[str, Any], str]:
    """Return recent messages from one mock Slack channel."""
    channel = MOCK_SLACK.get(args.channel_id, {"messages": []})
    messages = channel["messages"][: args.limit]
    result = {"channel_id": args.channel_id, "messages": messages}
    return result, f"{len(messages)} Slack messages returned from {args.channel_id}"


def fetch_gdrive_doc(args: FetchGdriveDocArgs) -> tuple[dict[str, Any], str]:
    """Return one mock Google Drive document."""
    doc = MOCK_DOCS[args.doc_id]
    result = {"doc_id": args.doc_id, "title": doc["title"], "content": doc["content"]}
    return result, f"document returned: {doc['title']}"
