import xml.etree.ElementTree as ET
from datetime import date
from feed_builder import build_feed_xml, build_digest_html


def test_build_digest_html_has_all_sections():
    digest = {
        "hot_topics": [
            {
                "title": "OpenAI 发布 GPT-5",
                "summary": "OpenAI 正式发布 GPT-5。",
                "articles": [
                    {"title": "GPT-5 released", "feed": "Ars Technica", "url": "https://ars.com/1"},
                    {"title": "GPT-5 analysis", "feed": "Bloomberg", "url": "https://bloom.com/1"},
                ],
            }
        ],
        "must_read": [
            {"title": "microgpt", "feed": "Andrej Karpathy blog", "url": "https://karpathy.github.io/1", "summary": "200 行实现 GPT。"},
        ],
        "notable": [
            {"title": "SQLite news", "feed": "HN", "url": "https://hn.com/1", "summary": "SQLite 更新。"},
        ],
    }
    html = build_digest_html(digest)
    assert "热点话题" in html
    assert "OpenAI 发布 GPT-5" in html
    assert "Ars Technica" in html
    assert "https://ars.com/1" in html
    assert "2 篇报道" in html
    assert "必读" in html
    assert "microgpt" in html
    assert "值得关注" in html
    assert "SQLite news" in html


def test_build_feed_xml_valid_rss():
    digest = {
        "hot_topics": [],
        "must_read": [
            {"title": "Test", "feed": "F", "url": "https://example.com", "summary": "Summary."},
        ],
        "notable": [],
    }
    xml_str = build_feed_xml(digest, today=date(2026, 4, 1), existing_items=[])
    root = ET.fromstring(xml_str)
    assert root.tag == "rss"
    channel = root.find("channel")
    assert channel.find("title").text == "每日速览"
    items = channel.findall("item")
    assert len(items) == 1
    assert "2026-04-01" in items[0].find("title").text
    assert "Test" in items[0].find("description").text


def test_build_feed_xml_preserves_history():
    digest = {"hot_topics": [], "must_read": [], "notable": []}
    old_item = '<item><title>每日速览 — 2026-03-31</title><guid>digest-2026-03-31</guid><pubDate>Mon, 31 Mar 2026 08:00:00 +0800</pubDate><description>old</description></item>'
    xml_str = build_feed_xml(digest, today=date(2026, 4, 1), existing_items=[old_item])
    root = ET.fromstring(xml_str)
    items = root.find("channel").findall("item")
    assert len(items) == 2
    titles = [item.find("title").text for item in items]
    assert "每日速览 — 2026-04-01" in titles
    assert "每日速览 — 2026-03-31" in titles
