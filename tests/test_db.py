from botlite import db


def test_db_init_and_stats(tmp_path, monkeypatch):
    test_db = tmp_path / "test_media.db"
    monkeypatch.setattr(db, "DB_FILE", str(test_db))

    db.init()

    # Initial stats should be 0
    assert db.get_stat("total_downloads") == 0
    assert db.get_stat("failed_downloads") == 0
    assert db.get_stat("nonexistent_stat") == 0

    # Increment
    db.increment("total_downloads")
    assert db.get_stat("total_downloads") == 1
    db.increment("total_downloads")
    assert db.get_stat("total_downloads") == 2
    assert db.get_stat("failed_downloads") == 0

    db.increment("failed_downloads")
    assert db.get_stat("failed_downloads") == 1

    # Calling init() again should not reset stats
    db.init()
    assert db.get_stat("total_downloads") == 2


def test_db_ban_unban(tmp_path, monkeypatch):
    test_db = tmp_path / "test_media.db"
    monkeypatch.setattr(db, "DB_FILE", str(test_db))

    db.init()

    user_id = 987654321
    assert not db.is_banned(user_id)

    db.ban(user_id)
    assert db.is_banned(user_id)

    # Idempotent ban
    db.ban(user_id)
    assert db.is_banned(user_id)

    db.unban(user_id)
    assert not db.is_banned(user_id)

    # Unban when not banned
    db.unban(user_id)
    assert not db.is_banned(user_id)
