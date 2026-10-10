from unittest.mock import patch

from botlite.downloader.cookies import resolve


def test_resolve_cookie_file_found():
    with patch("os.path.exists", side_effect=lambda p: p == "cookiesyoutube.txt"):
        assert resolve("https://www.youtube.com/watch?v=abc") == "cookiesyoutube.txt"


def test_resolve_cookie_file_not_found_and_invalid_url():
    with patch("os.path.exists", return_value=False):
        assert resolve("https://example.invalid/path") is None
        # Verify host parts with len <= 2 (e.g. 'co', 'uk') are skipped
        assert resolve("https://video.co.uk/watch") is None

    # Should fail closed and return None on unexpected parse/runtime issue
    with patch("botlite.downloader.cookies.urlparse", side_effect=Exception("bad")):
        assert resolve("not-a-url") is None
