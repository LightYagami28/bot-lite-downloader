from botlite.handlers.access import is_message_allowed


def _allowed(**overrides) -> bool:
    values = {
        "is_private": False,
        "is_group": True,
        "chat_id": -1001234567890,
        "sender_id": 123456789,
        "allow_groups": True,
        "allowed_group_ids": {-1001234567890},
    }
    values.update(overrides)
    return is_message_allowed(**values)


def test_private_user_is_allowed_without_group_configuration():
    assert _allowed(
        is_private=True,
        is_group=False,
        chat_id=123456789,
        allow_groups=False,
        allowed_group_ids=set(),
    )


def test_allowlisted_group_user_is_allowed():
    assert _allowed()


def test_group_is_denied_when_group_support_is_disabled():
    assert not _allowed(allow_groups=False)


def test_group_is_denied_when_chat_id_is_not_allowlisted():
    assert not _allowed(chat_id=-1009876543210)


def test_channel_is_denied_even_if_its_id_is_allowlisted():
    assert not _allowed(is_group=False)


def test_missing_chat_id_is_denied():
    assert not _allowed(chat_id=None)


def test_anonymous_or_non_user_sender_is_denied():
    assert not _allowed(sender_id=None)
    assert not _allowed(sender_id=-1001234567890)
