"""Authorization helpers shared by the Telegram handlers."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from telethon import events

from botlite.config import ALLOW_GROUPS, ALLOWED_GROUP_IDS


@dataclass(frozen=True)
class MessageOrigin:
    """Where a Telegram message came from."""

    private: bool
    group: bool
    chat_id: int | None
    sender_id: int | None


def _group_allowed(
    origin: MessageOrigin,
    allow_groups: bool,
    allowed_group_ids: Collection[int],
) -> bool:
    """Return whether the group chat is allowlisted when group chats are allowed.

    Args:
        origin: Origin of the message.
        allow_groups: Whether groups are accepted at all.
        allowed_group_ids: Set of allowed group/chat identifiers.

    Returns:
        ``True`` when the chat is part of the allowlist.
    """
    if not (allow_groups and origin.group):
        return False
    return origin.chat_id is not None and origin.chat_id in allowed_group_ids


def is_message_allowed(
    origin: MessageOrigin,
    allow_groups: bool,
    allowed_group_ids: Collection[int],
) -> bool:
    """Allow a real user in private chats or in an allowlisted group only.

    Args:
        origin: Origin of the message.
        allow_groups: Whether groups are accepted at all.
        allowed_group_ids: Set of allowed group/chat identifiers.

    Returns:
        ``True`` when the message passes the authorization policy.
    """
    if origin.sender_id is None or origin.sender_id <= 0:
        return False
    return origin.private or _group_allowed(origin, allow_groups, allowed_group_ids)


def origin_of(event: events.Event) -> MessageOrigin:
    """Describe where a Telethon event came from.

    Args:
        event: Telethon update event.

    Returns:
        Structured origin of the event.
    """
    return MessageOrigin(event.is_private, event.is_group, event.chat_id, event.sender_id)


def group_allowed(event: events.Event) -> bool:
    """Apply the configured group policy to a Telethon event.

    Args:
        event: Telethon update event.

    Returns:
        ``True`` when the event is authorized.
    """
    return is_message_allowed(origin_of(event), ALLOW_GROUPS, ALLOWED_GROUP_IDS)
