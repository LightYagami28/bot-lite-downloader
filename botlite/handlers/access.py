"""Authorization helpers shared by Telegram handlers."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from botlite.config import ALLOW_GROUPS, ALLOWED_GROUP_IDS


@dataclass(frozen=True)
class MessageOrigin:
    """Where a message came from."""

    is_private: bool
    is_group: bool
    chat_id: int | None
    sender_id: int | None


def is_message_allowed(
    origin: MessageOrigin,
    allow_groups: bool,
    allowed_group_ids: Collection[int],
) -> bool:
    """Allow a real user in private chats or an allowlisted group only."""
    if origin.sender_id is None or origin.sender_id <= 0:
        return False
    if origin.is_private:
        return True
    return (
        allow_groups
        and origin.is_group
        and origin.chat_id is not None
        and origin.chat_id in allowed_group_ids
    )


def group_allowed(event) -> bool:
    """Apply the configured group policy to a Telethon event."""
    origin = MessageOrigin(event.is_private, event.is_group, event.chat_id, event.sender_id)
    return is_message_allowed(origin, ALLOW_GROUPS, ALLOWED_GROUP_IDS)
