"""Tool-specific permission checks."""

from pydantic import BaseModel

from src.mock_data import MOCK_DOCS, SLACK_CHANNEL_WHITELIST
from src.models import (
    Brand,
    FetchGdriveDocArgs,
    GetSlackMessagesArgs,
    SearchPrsArgs,
)


class PermissionDecision(BaseModel):
    """Permission result with a reviewer-readable denial reason."""

    allowed: bool
    denial_reason: str | None = None


def allow() -> PermissionDecision:
    """Return an allowed permission decision."""
    return PermissionDecision(allowed=True)


def deny(reason: str) -> PermissionDecision:
    """Return a denied permission decision."""
    return PermissionDecision(allowed=False, denial_reason=reason)


def can_search_prs(caller_brand: Brand, args: SearchPrsArgs) -> PermissionDecision:
    """PR search permission is strict brand equality."""
    if caller_brand == args.brand:
        return allow()
    return deny("caller brand cannot search another brand's PRs")


def can_get_slack_messages(
    caller_brand: Brand,
    args: GetSlackMessagesArgs,
) -> PermissionDecision:
    """Slack permission is based on a caller-brand channel whitelist."""
    allowed_channels = SLACK_CHANNEL_WHITELIST[caller_brand]
    if args.channel_id in allowed_channels:
        return allow()
    return deny("caller brand is not allowed to read this Slack channel")


def can_fetch_gdrive_doc(
    caller_brand: Brand,
    args: FetchGdriveDocArgs,
) -> PermissionDecision:
    """GDrive permission uses the actual document metadata brand."""
    doc = MOCK_DOCS.get(args.doc_id)
    if doc is None:
        return deny("document does not exist")
    if doc["brand"] == caller_brand:
        return allow()
    return deny("caller brand cannot read this document")
