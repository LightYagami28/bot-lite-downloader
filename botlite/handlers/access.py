"""Authorization helpers shared by Telegram handlers."""

from __future__ import annotations

from collections.abc import Collection


def is_message_allowed(
    *,
    is_private: bool,
    is_group: bool,
    chat_id: int | None,
    sender_id: int | None,
    allow_groups: bool,
    allowed_group_ids: Collection[int],
) -> bool:
    """Allow a real user in private chats or an allowlisted group only."""
    if sender_id is None or sender_id <= 0:
        return False
    if is_private:
        return True
    return (
        allow_groups
        and is_group
        and chat_id is not None
        and chat_id in allowed_group_ids
    )
