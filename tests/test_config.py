from botlite.config import _int_list, _nonzero_int_list


def test_int_list_keeps_signed_decimal_ids_and_ignores_malformed_items(monkeypatch):
    monkeypatch.setenv("TEST_ID_LIST", "-100123, 42, --7, nope, 0, +9, ,")

    assert _int_list("TEST_ID_LIST") == [-100123, 42, 0, 9]
    assert _nonzero_int_list("TEST_ID_LIST") == {-100123, 42, 9}
