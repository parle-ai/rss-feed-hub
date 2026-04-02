import os
from unittest.mock import patch, Mock
from datetime import date
from main import run_digest


def test_run_digest_creates_feed_xml(tmp_path):
    articles = [
        {"id": 1, "title": "T1", "feed": "F1", "url": "https://example.com/1",
         "content": "Content one.", "excerpt": "Content one.", "published_at": "2026-04-01T06:00:00Z"},
    ]
    cluster_result = {
        "hot_topics": [],
        "must_read": [1],
        "notable": {},
        "filtered_out": [],
    }
    digest_result = {
        "hot_topics": [],
        "must_read": [{"title": "T1", "feed": "F1", "url": "https://example.com/1", "summary": "摘要。"}],
        "notable": {},
    }

    output_path = str(tmp_path / "feed.xml")

    with patch("main.fetch_entries", return_value=articles), \
         patch("main.filter_and_cluster", return_value=cluster_result), \
         patch("main.generate_digest_summaries", return_value=digest_result), \
         patch("main.load_config") as mock_config:
        mock_config.return_value = {
            "must_read_feeds": ["F1"],
            "digest": {"lookback_hours": 24, "history_days": 30},
            "claude": {"model": "claude-haiku-4-5-20251001", "max_article_length": 2000, "max_cluster_article_length": 500},
        }
        run_digest(output_path=output_path)

    assert os.path.exists(output_path)
    content = open(output_path).read()
    assert "每日速览" in content
    assert "T1" in content


def test_run_digest_skips_when_no_articles(tmp_path):
    output_path = str(tmp_path / "feed.xml")

    with patch("main.fetch_entries", return_value=[]), \
         patch("main.load_config") as mock_config:
        mock_config.return_value = {
            "must_read_feeds": [],
            "digest": {"lookback_hours": 24, "history_days": 30},
            "claude": {"model": "claude-haiku-4-5-20251001", "max_article_length": 2000, "max_cluster_article_length": 500},
        }
        run_digest(output_path=output_path)

    assert not os.path.exists(output_path)


def test_run_digest_skips_when_clustering_fails(tmp_path):
    articles = [{"id": 1, "title": "T", "feed": "F", "url": "https://example.com", "content": "C", "excerpt": "E", "published_at": "2026-04-01T06:00:00Z"}]
    output_path = str(tmp_path / "feed.xml")

    with patch("main.fetch_entries", return_value=articles), \
         patch("main.filter_and_cluster", return_value=None), \
         patch("main.load_config") as mock_config:
        mock_config.return_value = {
            "must_read_feeds": [],
            "digest": {"lookback_hours": 24, "history_days": 30},
            "claude": {"model": "claude-haiku-4-5-20251001", "max_article_length": 2000, "max_cluster_article_length": 500},
        }
        run_digest(output_path=output_path)

    assert not os.path.exists(output_path)
