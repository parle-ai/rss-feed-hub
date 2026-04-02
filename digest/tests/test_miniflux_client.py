import json
from unittest.mock import patch, Mock
from miniflux_client import fetch_entries


def _mock_response(entries, total):
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {"total": total, "entries": entries}
    return resp


def test_fetch_entries_returns_articles():
    entries = [
        {
            "id": 1,
            "title": "Test Article",
            "url": "https://example.com/1",
            "content": "This is the first sentence. This is the second sentence. More text here.",
            "feed": {"title": "Test Feed"},
            "published_at": "2026-04-01T06:00:00Z",
        }
    ]
    with patch("miniflux_client.requests.get", return_value=_mock_response(entries, 1)):
        result = fetch_entries(
            base_url="http://miniflux:8080",
            api_key="test-key",
            lookback_hours=24,
        )
    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["title"] == "Test Article"
    assert result[0]["feed"] == "Test Feed"
    assert result[0]["url"] == "https://example.com/1"
    assert "excerpt" in result[0]
    assert "content" in result[0]


def test_fetch_entries_paginates():
    page1 = [{"id": i, "title": f"A{i}", "url": f"https://example.com/{i}",
              "content": "Short.", "feed": {"title": "F"}, "published_at": "2026-04-01T06:00:00Z"}
             for i in range(100)]
    page2 = [{"id": 100, "title": "A100", "url": "https://example.com/100",
              "content": "Short.", "feed": {"title": "F"}, "published_at": "2026-04-01T06:00:00Z"}]

    responses = [_mock_response(page1, 101), _mock_response(page2, 101)]
    with patch("miniflux_client.requests.get", side_effect=responses):
        result = fetch_entries("http://miniflux:8080", "key", 24)
    assert len(result) == 101


def test_fetch_entries_extracts_excerpt():
    entries = [
        {
            "id": 1, "title": "T", "url": "https://example.com/1",
            "content": "<p>First sentence. Second sentence. Third sentence.</p>",
            "feed": {"title": "F"}, "published_at": "2026-04-01T06:00:00Z",
        }
    ]
    with patch("miniflux_client.requests.get", return_value=_mock_response(entries, 1)):
        result = fetch_entries("http://miniflux:8080", "key", 24)
    assert "First sentence. Second sentence." in result[0]["excerpt"]
