# Daily Digest RSS Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily digest service that pulls articles from Miniflux, uses Claude AI to filter/cluster/summarize them in Chinese, and outputs a standard RSS feed subscribable in NetNewsWire.

**Architecture:** A Python script (`digest-worker`) runs daily via supercronic inside Docker. It calls Miniflux API for articles, Claude Haiku for filtering + summarization, and writes a static `feed.xml`. An nginx container serves the XML over HTTP on port 8888.

**Tech Stack:** Python 3.12, anthropic SDK, requests, Docker, supercronic, nginx

---

## File Structure

```
digest/
├── Dockerfile           # Python 3.12-slim + supercronic, runs cron
├── crontab              # Schedule: daily 08:00
├── requirements.txt     # anthropic, requests, pyyaml
├── config.yaml          # Must-read feeds, Claude model, digest params
├── main.py              # Entry point: orchestrates fetch → AI → build → write
├── miniflux_client.py   # Miniflux API client: fetch entries
├── summarize.py         # Claude API: Step 1 (filter/cluster) + Step 2 (summarize)
├── feed_builder.py      # Build RSS XML from digest data
└── tests/
    ├── test_miniflux_client.py
    ├── test_summarize.py
    ├── test_feed_builder.py
    └── test_main.py
```

---

### Task 1: Project scaffold + config

**Files:**
- Create: `digest/requirements.txt`
- Create: `digest/config.yaml`
- Create: `digest/Dockerfile`
- Create: `digest/crontab`

- [ ] **Step 1: Create requirements.txt**

```
anthropic>=0.42.0
requests>=2.31.0
pyyaml>=6.0
pytest>=8.0
```

- [ ] **Step 2: Create config.yaml**

```yaml
must_read_feeds:
  - "Andrej Karpathy blog"

digest:
  lookback_hours: 24
  history_days: 30

claude:
  model: "claude-haiku-4-5-20251001"
  max_article_length: 2000
  max_cluster_article_length: 500
```

- [ ] **Step 3: Create crontab**

```
0 8 * * * cd /app && python main.py >> /var/log/digest.log 2>&1
```

- [ ] **Step 4: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

# Install supercronic
ARG SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64
ARG SUPERCRONIC_SHA=71b0d58cc53f6bd72cf2f293e09e294b79c666d8
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL "${SUPERCRONIC_URL}" -o /usr/local/bin/supercronic && \
    echo "${SUPERCRONIC_SHA}  /usr/local/bin/supercronic" | sha1sum -c - && \
    chmod +x /usr/local/bin/supercronic && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["supercronic", "/app/crontab"]
```

- [ ] **Step 5: Commit**

```bash
git add digest/requirements.txt digest/config.yaml digest/crontab digest/Dockerfile
git commit -m "feat(digest): add project scaffold, config, and Dockerfile"
```

---

### Task 2: Miniflux API client

**Files:**
- Create: `digest/miniflux_client.py`
- Create: `digest/tests/test_miniflux_client.py`

- [ ] **Step 1: Write the failing test**

Create `digest/tests/test_miniflux_client.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd digest && python -m pytest tests/test_miniflux_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'miniflux_client'`

- [ ] **Step 3: Write miniflux_client.py**

Create `digest/miniflux_client.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd digest && python -m pytest tests/test_miniflux_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add digest/miniflux_client.py digest/tests/test_miniflux_client.py
git commit -m "feat(digest): add Miniflux API client with pagination"
```

---

### Task 3: Claude AI — Step 1 filter + cluster

**Files:**
- Create: `digest/summarize.py`
- Create: `digest/tests/test_summarize.py`

- [ ] **Step 1: Write the failing test for filter_and_cluster**

Create `digest/tests/test_summarize.py`:

```python
import json
from unittest.mock import patch, Mock
from summarize import filter_and_cluster, generate_summary


def _mock_claude_response(text):
    mock_msg = Mock()
    mock_block = Mock()
    mock_block.text = text
    mock_msg.content = [mock_block]
    return mock_msg


def test_filter_and_cluster_parses_response():
    articles = [
        {"id": 1, "title": "GPT-5 released", "feed": "Ars Technica", "excerpt": "OpenAI launches GPT-5."},
        {"id": 2, "title": "Karpathy post", "feed": "Andrej Karpathy blog", "excerpt": "New blog post."},
        {"id": 3, "title": "GPT-5 analysis", "feed": "Bloomberg", "excerpt": "Analysis of GPT-5."},
        {"id": 4, "title": "Random spam", "feed": "Some Feed", "excerpt": "Low value."},
    ]
    claude_response = json.dumps({
        "hot_topics": [
            {"title": "OpenAI 发布 GPT-5", "article_ids": [1, 3], "reason": "多家媒体报道"}
        ],
        "must_read": [2],
        "notable": [],
        "filtered_out": [4],
    })
    must_read_feeds = ["Andrej Karpathy blog"]

    with patch("summarize.anthropic") as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(claude_response)

        result = filter_and_cluster(articles, must_read_feeds, model="claude-haiku-4-5-20251001")

    assert len(result["hot_topics"]) == 1
    assert result["hot_topics"][0]["title"] == "OpenAI 发布 GPT-5"
    assert result["hot_topics"][0]["article_ids"] == [1, 3]
    assert result["must_read"] == [2]
    assert result["filtered_out"] == [4]


def test_filter_and_cluster_handles_api_error():
    articles = [{"id": 1, "title": "T", "feed": "F", "excerpt": "E"}]

    with patch("summarize.anthropic") as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API error")

        result = filter_and_cluster(articles, [], model="claude-haiku-4-5-20251001")

    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd digest && python -m pytest tests/test_summarize.py::test_filter_and_cluster_parses_response -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'summarize'`

- [ ] **Step 3: Write summarize.py — filter_and_cluster function**

Create `digest/summarize.py`:

```python
import json
import anthropic

FILTER_SYSTEM_PROMPT = """你是一个新闻编辑助手。你的任务是分析一批 RSS 文章，完成以下工作：

1. **热点话题识别**：找出被多个来源报道的同一事件/话题，将它们合并为一个话题。按报道数量和重要性排序。
2. **必读标记**：来自以下 feed 的文章必须单独展示（即使它属于某个热点话题，也要同时在必读区出现）：{must_read_feeds}
3. **值得关注**：不属于热点、不属于必读，但仍有阅读价值的文章。
4. **过滤**：纯噪音、重复性极高的低价值内容不要包含。

输出严格 JSON 格式：
{{
  "hot_topics": [
    {{
      "title": "话题标题（中文）",
      "article_ids": [1, 3, 7],
      "reason": "为什么这是热点（一句话）"
    }}
  ],
  "must_read": [5, 12],
  "notable": [2, 8, 15],
  "filtered_out": [4, 6, 9]
}}"""

TOPIC_SUMMARY_SYSTEM_PROMPT = (
    "你是一个新闻摘要助手。根据以下多篇关于同一话题的报道，"
    "生成一段中文摘要（3-5 句话），综合各来源的核心信息。技术术语保留英文。"
)

SINGLE_SUMMARY_SYSTEM_PROMPT = (
    "你是一个文章摘要助手。用中文写一段 2-3 句话的摘要，"
    "概括文章核心观点。技术术语保留英文。"
)


def filter_and_cluster(articles, must_read_feeds, model):
    client = anthropic.Anthropic()

    articles_for_prompt = [
        {"id": a["id"], "title": a["title"], "feed": a["feed"], "excerpt": a["excerpt"]}
        for a in articles
    ]

    system = FILTER_SYSTEM_PROMPT.format(must_read_feeds=", ".join(must_read_feeds))
    user = f"以下是过去 24 小时的 {len(articles)} 篇文章：\n\n{json.dumps(articles_for_prompt, ensure_ascii=False)}\n\n请分析并输出 JSON。"

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return json.loads(response.content[0].text)
    except Exception:
        return None


def generate_summary(content, system_prompt, model):
    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd digest && python -m pytest tests/test_summarize.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add digest/summarize.py digest/tests/test_summarize.py
git commit -m "feat(digest): add Claude AI filter/cluster and summary generation"
```

---

### Task 4: Claude AI — Step 2 batch summarization

**Files:**
- Modify: `digest/summarize.py` (add `generate_digest_summaries`)
- Modify: `digest/tests/test_summarize.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `digest/tests/test_summarize.py`:

```python
def test_generate_digest_summaries_for_topics():
    articles = [
        {"id": 1, "title": "GPT-5 released", "feed": "Ars Technica", "url": "https://ars.com/1", "content": "OpenAI has released GPT-5 with major improvements.", "excerpt": ""},
        {"id": 3, "title": "GPT-5 analysis", "feed": "Bloomberg", "url": "https://bloom.com/1", "content": "Bloomberg analysis of GPT-5 launch.", "excerpt": ""},
        {"id": 2, "title": "Karpathy post", "feed": "Andrej Karpathy blog", "url": "https://karpathy.github.io/1", "content": "New post about microgpt implementation.", "excerpt": ""},
    ]
    cluster_result = {
        "hot_topics": [{"title": "OpenAI 发布 GPT-5", "article_ids": [1, 3], "reason": "多家报道"}],
        "must_read": [2],
        "notable": [],
        "filtered_out": [],
    }

    with patch("summarize.anthropic") as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response("这是AI生成的中文摘要。")

        result = generate_digest_summaries(articles, cluster_result, model="claude-haiku-4-5-20251001", max_article_length=2000, max_cluster_article_length=500)

    assert len(result["hot_topics"]) == 1
    assert result["hot_topics"][0]["summary"] == "这是AI生成的中文摘要。"
    assert result["hot_topics"][0]["articles"][0]["feed"] == "Ars Technica"
    assert len(result["must_read"]) == 1
    assert result["must_read"][0]["summary"] == "这是AI生成的中文摘要。"


def test_generate_digest_summaries_fallback_on_error():
    articles = [
        {"id": 1, "title": "T", "feed": "F", "url": "https://example.com", "content": "Fallback content here for testing purposes.", "excerpt": ""},
    ]
    cluster_result = {"hot_topics": [], "must_read": [1], "notable": [], "filtered_out": []}

    with patch("summarize.anthropic") as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API down")

        result = generate_digest_summaries(articles, cluster_result, model="claude-haiku-4-5-20251001", max_article_length=2000, max_cluster_article_length=500)

    assert result["must_read"][0]["summary"] == "Fallback content here for testing purposes."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd digest && python -m pytest tests/test_summarize.py::test_generate_digest_summaries_for_topics -v`
Expected: FAIL — `ImportError: cannot import name 'generate_digest_summaries'`

- [ ] **Step 3: Add generate_digest_summaries to summarize.py**

Append to `digest/summarize.py`:

```python
def _find_article(articles, article_id):
    for a in articles:
        if a["id"] == article_id:
            return a
    return None


def _truncate(text, max_length):
    text = text or ""
    return text[:max_length] if len(text) > max_length else text


def generate_digest_summaries(articles, cluster_result, model, max_article_length, max_cluster_article_length):
    digest = {"hot_topics": [], "must_read": [], "notable": []}

    for topic in cluster_result.get("hot_topics", []):
        topic_articles = []
        prompt_parts = [f"话题：{topic['title']}\n"]
        for i, aid in enumerate(topic["article_ids"], 1):
            article = _find_article(articles, aid)
            if not article:
                continue
            content = _truncate(article["content"], max_cluster_article_length)
            prompt_parts.append(f"报道 {i}（{article['feed']}）：{content}")
            topic_articles.append({
                "title": article["title"],
                "feed": article["feed"],
                "url": article["url"],
            })

        summary = generate_summary(
            "\n\n".join(prompt_parts),
            TOPIC_SUMMARY_SYSTEM_PROMPT,
            model,
        )
        if summary is None:
            first = _find_article(articles, topic["article_ids"][0])
            summary = _truncate(first["content"], 200) if first else ""

        digest["hot_topics"].append({
            "title": topic["title"],
            "summary": summary,
            "articles": topic_articles,
        })

    for category in ("must_read", "notable"):
        for aid in cluster_result.get(category, []):
            article = _find_article(articles, aid)
            if not article:
                continue
            content = _truncate(article["content"], max_article_length)
            prompt = f"标题：{article['title']}\n来源：{article['feed']}\n正文：{content}"

            summary = generate_summary(prompt, SINGLE_SUMMARY_SYSTEM_PROMPT, model)
            if summary is None:
                summary = _truncate(article["content"], 200)

            digest[category].append({
                "title": article["title"],
                "feed": article["feed"],
                "url": article["url"],
                "summary": summary,
            })

    return digest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd digest && python -m pytest tests/test_summarize.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add digest/summarize.py digest/tests/test_summarize.py
git commit -m "feat(digest): add batch summarization with fallback"
```

---

### Task 5: RSS feed builder

**Files:**
- Create: `digest/feed_builder.py`
- Create: `digest/tests/test_feed_builder.py`

- [ ] **Step 1: Write the failing test**

Create `digest/tests/test_feed_builder.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd digest && python -m pytest tests/test_feed_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'feed_builder'`

- [ ] **Step 3: Write feed_builder.py**

Create `digest/feed_builder.py`:

```python
from datetime import date
from email.utils import format_datetime
from datetime import datetime, timezone, timedelta


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
        for a in digest["notable"]:
            parts.append(f'<h3><a href="{a["url"]}">{a["title"]}</a></h3>')
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

    new_item = (
        f"<item>"
        f"<title>{title}</title>"
        f"<guid>{guid}</guid>"
        f"<pubDate>{pub_date}</pubDate>"
        f"<description><![CDATA[{html}]]></description>"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd digest && python -m pytest tests/test_feed_builder.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add digest/feed_builder.py digest/tests/test_feed_builder.py
git commit -m "feat(digest): add RSS feed XML builder"
```

---

### Task 6: Main entry point

**Files:**
- Create: `digest/main.py`
- Create: `digest/tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Create `digest/tests/test_main.py`:

```python
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
        "notable": [],
        "filtered_out": [],
    }
    digest_result = {
        "hot_topics": [],
        "must_read": [{"title": "T1", "feed": "F1", "url": "https://example.com/1", "summary": "摘要。"}],
        "notable": [],
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd digest && python -m pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Write main.py**

Create `digest/main.py`:

```python
import os
import re
import yaml
from datetime import date

from miniflux_client import fetch_entries
from summarize import filter_and_cluster, generate_digest_summaries
from feed_builder import build_feed_xml


def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def _parse_existing_items(feed_path, max_days):
    if not os.path.exists(feed_path):
        return []
    with open(feed_path) as f:
        content = f.read()
    items = re.findall(r"<item>.*?</item>", content, re.DOTALL)
    return items[:max_days]


def run_digest(output_path="/output/feed.xml"):
    config = load_config()

    base_url = os.environ.get("MINIFLUX_URL", "http://miniflux:8080")
    api_key = os.environ.get("MINIFLUX_API_KEY", "")

    articles = fetch_entries(base_url, api_key, config["digest"]["lookback_hours"])

    if not articles:
        print("No articles found, skipping digest generation.")
        return

    cluster_result = filter_and_cluster(
        articles,
        config["must_read_feeds"],
        model=config["claude"]["model"],
    )

    if cluster_result is None:
        print("Clustering failed, skipping digest generation.")
        return

    digest = generate_digest_summaries(
        articles,
        cluster_result,
        model=config["claude"]["model"],
        max_article_length=config["claude"]["max_article_length"],
        max_cluster_article_length=config["claude"]["max_cluster_article_length"],
    )

    existing_items = _parse_existing_items(output_path, config["digest"]["history_days"])
    xml = build_feed_xml(digest, today=date.today(), existing_items=existing_items)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml)

    topic_count = len(digest["hot_topics"])
    must_read_count = len(digest["must_read"])
    notable_count = len(digest["notable"])
    print(f"Digest generated: {topic_count} topics, {must_read_count} must-read, {notable_count} notable")


if __name__ == "__main__":
    run_digest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd digest && python -m pytest tests/test_main.py -v`
Expected: 3 passed

- [ ] **Step 5: Run all tests**

Run: `cd digest && python -m pytest tests/ -v`
Expected: 10 passed

- [ ] **Step 6: Commit**

```bash
git add digest/main.py digest/tests/test_main.py
git commit -m "feat(digest): add main entry point orchestrating full pipeline"
```

---

### Task 7: Docker Compose integration

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create: `digest/tests/__init__.py`

- [ ] **Step 1: Create empty test init file**

Create `digest/tests/__init__.py` as an empty file.

- [ ] **Step 2: Update docker-compose.yml**

Add after the `db` service in `docker-compose.yml`:

```yaml
  digest-worker:
    build: ./digest
    volumes:
      - digest-output:/output
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MINIFLUX_URL=http://miniflux:8080
      - MINIFLUX_API_KEY=${MINIFLUX_API_KEY}
    depends_on:
      miniflux:
        condition: service_healthy
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "8888:80"
    volumes:
      - digest-output:/usr/share/nginx/html:ro
    restart: unless-stopped
```

Add `digest-output:` under the `volumes:` section (alongside `miniflux-db:`).

- [ ] **Step 3: Update .env.example**

Add to the end of `.env.example`:

```
# Digest (Daily AI Summary)
ANTHROPIC_API_KEY=sk-ant-...
MINIFLUX_API_KEY=
```

- [ ] **Step 4: Verify docker-compose config is valid**

Run: `docker compose config --quiet`
Expected: exits 0 with no output (valid config)

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml .env.example digest/tests/__init__.py
git commit -m "feat(digest): integrate digest-worker and nginx into docker-compose"
```

---

### Task 8: Build and smoke test

**Files:** No new files — integration verification.

- [ ] **Step 1: Build digest-worker image**

Run: `docker compose build digest-worker`
Expected: Successfully built

- [ ] **Step 2: Run digest manually to test end-to-end**

The user must first:
1. Add `ANTHROPIC_API_KEY` to `.env` (their Claude API key)
2. Generate a Miniflux API key: open `http://localhost:8080`, go to Settings → API Keys → Create
3. Add `MINIFLUX_API_KEY` to `.env`

Then run:
```bash
docker compose run --rm digest-worker python main.py
```

Expected: Output like `Digest generated: N topics, N must-read, N notable`

- [ ] **Step 3: Verify feed.xml was created**

Run: `docker compose run --rm nginx cat /usr/share/nginx/html/feed.xml | head -20`
Expected: Valid RSS XML starting with `<?xml version="1.0"` containing `每日速览`

- [ ] **Step 4: Start nginx and verify HTTP access**

Run: `docker compose up -d nginx`
Then: `curl -s http://localhost:8888/feed.xml | head -5`
Expected: RSS XML served over HTTP

- [ ] **Step 5: Bring up all services**

Run: `docker compose up -d`
Expected: All services running including digest-worker (waiting for next cron trigger)

- [ ] **Step 6: Commit any fixes**

If any fixes were needed during smoke testing, commit them:
```bash
git add -A
git commit -m "fix(digest): fixes from integration smoke test"
```

---

### Task 9: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Add to the Architecture table:

```markdown
| Digest Worker | AI-powered daily digest — filters, clusters, summarizes articles | cron (internal) |
| nginx | Serves digest RSS feed | 8888 |
```

Add a new section after "Current Feeds":

```markdown
## Daily Digest

AI-powered daily summary of your feeds — hot topics, must-reads, and notable articles, all in Chinese.

**Subscribe in NetNewsWire:** `http://localhost:8888/feed.xml`

Runs daily at 08:00. Configure must-read feeds in `digest/config.yaml`.

Requires: `ANTHROPIC_API_KEY` and `MINIFLUX_API_KEY` in `.env`.
```

Update the `.env.example` section in Quick Start if present.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add Daily Digest section to README"
```
