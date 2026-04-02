import re
import requests
from datetime import datetime, timedelta, timezone


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text)


def _extract_excerpt(content, num_sentences=2):
    text = _strip_html(content)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:num_sentences])


def fetch_entries(base_url, api_key, lookback_hours):
    after = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    after_ts = int(after.timestamp())

    headers = {"X-Auth-Token": api_key}
    articles = []
    offset = 0
    limit = 100

    while True:
        resp = requests.get(
            f"{base_url}/v1/entries",
            headers=headers,
            timeout=30,
            params={
                "status": "unread",
                "order": "published_at",
                "direction": "desc",
                "after": after_ts,
                "limit": limit,
                "offset": offset,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        for entry in data["entries"]:
            articles.append({
                "id": entry["id"],
                "title": entry["title"],
                "url": entry["url"],
                "feed": entry["feed"]["title"],
                "content": entry["content"],
                "excerpt": _extract_excerpt(entry["content"]),
                "published_at": entry["published_at"],
            })

        if offset + limit >= data["total"]:
            break
        offset += limit

    return articles
