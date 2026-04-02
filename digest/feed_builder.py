from datetime import date, datetime, timezone, timedelta
from email.utils import format_datetime
import xml.sax.saxutils as saxutils


def build_digest_html(digest):
    parts = []

    if digest["hot_topics"]:
        parts.append("<h2>热点话题</h2>")
        for i, topic in enumerate(digest["hot_topics"], 1):
            source_count = len(topic["articles"])
            source_list = "、".join(a["feed"] for a in topic["articles"])
            parts.append(f"<h3>{i}. {topic['title']}</h3>")
            parts.append(f"<p>{source_count} 篇报道：{source_list}</p>")
            parts.append(f"<p>{topic['summary']}</p>")
            parts.append("<ul>")
            for a in topic["articles"]:
                parts.append(f'<li><a href="{a["url"]}">{a["feed"]}</a></li>')
            parts.append("</ul>")

    if digest["must_read"]:
        parts.append("<h2>必读</h2>")
        for a in digest["must_read"]:
            parts.append(f"<h3>{a['title']}</h3>")
            parts.append(f"<p>{a['feed']}</p>")
            parts.append(f"<p>{a['summary']}</p>")
            parts.append(f'<p><a href="{a["url"]}">阅读原文 →</a></p>')

    if digest["notable"]:
        parts.append("<h2>值得关注</h2>")
        for category_name, category_articles in digest["notable"].items():
            parts.append(f"<h3>{category_name}</h3>")
            for a in category_articles:
                parts.append(f'<h4><a href="{a["url"]}">{a["title"]}</a></h4>')
                parts.append(f"<p>{a['summary']}</p>")

    return "\n".join(parts)


def _make_pub_date(d):
    dt = datetime(d.year, d.month, d.day, 8, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    return format_datetime(dt, usegmt=False)


def build_feed_xml(digest, today, existing_items):
    html = build_digest_html(digest)
    title = f"每日速览 — {today.isoformat()}"
    guid = f"digest-{today.isoformat()}"
    pub_date = _make_pub_date(today)

    # Use XML escaping so ET.fromstring() can parse the description
    escaped_html = saxutils.escape(html)

    new_item = (
        f"<item>"
        f"<title>{title}</title>"
        f"<guid>{guid}</guid>"
        f"<pubDate>{pub_date}</pubDate>"
        f"<description>{escaped_html}</description>"
        f"</item>"
    )

    all_items = [new_item] + existing_items

    items_xml = "\n".join(all_items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "<channel>\n"
        "<title>每日速览</title>\n"
        "<link>http://localhost:8888</link>\n"
        "<description>AI-powered daily digest from your RSS feeds</description>\n"
        f"{items_xml}\n"
        "</channel>\n"
        "</rss>"
    )
