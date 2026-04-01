# Daily Digest RSS Feed — Design Spec

## Overview

为 rss-feed-hub 新增一个 Daily Digest 功能：每天早上 8 点自动从 Miniflux 拉取过去 24 小时的文章，由 Claude AI 进行筛选、聚合去重、排序和中文摘要生成，输出为一个标准 RSS feed，供 NetNewsWire 直接订阅。

## Goals

- 每天 100+ 篇 unread 压缩成一份结构化的「每日速览」
- 同一热点事件多源报道自动合并，不重复阅读
- 所有摘要统一中文输出，快速扫读
- 在 NetNewsWire 里像普通 feed 一样阅读，无需新 app
- 零手动操作，Docker 内部 cron 自动运行

## Non-Goals

- 自定义 Web Dashboard（Phase 2 考虑）
- 实时/准实时推送（每天一次足够）
- 修改 NetNewsWire 客户端
- 多用户支持

## Architecture

```
┌──────────────┐     Miniflux API      ┌──────────────────┐     Claude API
│   Miniflux   │ ───────────────────▶  │  digest-worker   │ ──────────────▶ AI 筛选/摘要
│  (已有文章)   │                       │  (Python 脚本)    │
└──────────────┘                       └────────┬─────────┘
                                                │
                                          生成 feed.xml
                                                │
                                       ┌────────▼─────────┐
                                       │   nginx (静态)    │  ← NetNewsWire 订阅
                                       │   port: 8888      │     http://localhost:8888/feed.xml
                                       └──────────────────┘
```

### Components

**1. digest-worker（Python 脚本，Docker 容器）**

核心处理服务，由容器内 supercronic 每天 08:00 触发。

职责：
- 从 Miniflux API 拉取过去 24 小时的文章
- 调用 Claude API 进行筛选、聚合、摘要
- 生成 RSS XML 文件输出到共享 volume

**2. nginx（静态文件服务）**

轻量 HTTP 服务，将 `feed.xml` 暴露为可订阅的 RSS 端点。

- 端口：8888
- NetNewsWire 订阅地址：`http://localhost:8888/feed.xml`

**3. 新增到 docker-compose.yml**

两个新 service + 一个共享 volume，不新增数据库。

## AI 处理流程

### Step 1：筛选 + 聚合（Claude Haiku）

输入 100 篇文章的标题 + 前两句话（约 5K tokens），一次 API 调用完成：

- 识别热点话题：哪些文章在报道同一件事，合并为一个话题
- 标记必读：来自 must_read_feeds 的文章单独标记
- 标记值得关注：剩余有价值的独立文章
- 过滤噪音：低价值内容不进入 digest

**System Prompt：**

```
你是一个新闻编辑助手。你的任务是分析一批 RSS 文章，完成以下工作：

1. **热点话题识别**：找出被多个来源报道的同一事件/话题，将它们合并为一个话题。按报道数量和重要性排序。
2. **必读标记**：来自以下 feed 的文章必须单独展示（即使它属于某个热点话题，也要同时在必读区出现）：{must_read_feeds}
3. **值得关注**：不属于热点、不属于必读，但仍有阅读价值的文章。
4. **过滤**：纯噪音、重复性极高的低价值内容不要包含。

输出严格 JSON 格式：
{
  "hot_topics": [
    {
      "title": "话题标题（中文）",
      "article_ids": [1, 3, 7],
      "reason": "为什么这是热点（一句话）"
    }
  ],
  "must_read": [5, 12],
  "notable": [2, 8, 15],
  "filtered_out": [4, 6, 9]
}
```

**User Prompt：**

```
以下是过去 24 小时的 {count} 篇文章：

{articles_json}

请分析并输出 JSON。
```

其中 `articles_json` 格式：
```json
[
  {"id": 1, "title": "...", "feed": "Ars Technica", "excerpt": "前两句话..."},
  {"id": 2, "title": "...", "feed": "Karpathy blog", "excerpt": "..."}
]
```

### Step 2：生成摘要（Claude Haiku）

对 Step 1 筛选出的内容，分批调用 Claude 生成中文摘要：

**热点话题：** 将同一话题的所有文章正文（每篇截断 500 字）合并输入。

```
System: 你是一个新闻摘要助手。根据以下多篇关于同一话题的报道，生成一段中文摘要（3-5 句话），综合各来源的核心信息。技术术语保留英文。

User: 话题：{topic_title}

报道 1（{feed_name}）：{content}
报道 2（{feed_name}）：{content}
...
```

**必读/值得关注单篇：** 单篇文章正文（截断 2000 字）。

```
System: 你是一个文章摘要助手。用中文写一段 2-3 句话的摘要，概括文章核心观点。技术术语保留英文。

User: 标题：{title}
来源：{feed_name}
正文：{content}
```

### 容错

- Claude API 调用失败时，fallback 到文章前 200 字作为摘要
- 单篇失败不影响整体 digest 生成
- Step 1 失败时，跳过本次 digest 生成，下次运行时拉取更长时间窗口的文章

## RSS Feed 输出

每天生成一个 RSS item，结构化 HTML 作为内容：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>每日速览</title>
    <link>http://localhost:8888</link>
    <description>AI-powered daily digest from your RSS feeds</description>
    <item>
      <title>每日速览 — 2026-04-01</title>
      <pubDate>Wed, 01 Apr 2026 08:00:00 +0800</pubDate>
      <guid>digest-2026-04-01</guid>
      <description><![CDATA[
        <h2>热点话题</h2>
        <!-- 不设上限，有多少展示多少 -->
        <h3>1. {topic_title}</h3>
        <p>{source_count} 篇报道：{source_list}</p>
        <p>{ai_summary}</p>
        <ul>
          <li><a href="{url}">{feed_name}</a></li>
          ...
        </ul>

        <h2>必读</h2>
        <h3>{article_title}</h3>
        <p>{feed_name}</p>
        <p>{ai_summary}</p>
        <a href="{url}">阅读原文 →</a>

        <h2>值得关注</h2>
        <h3><a href="{url}">{article_title}</a></h3>
        <p>{ai_summary}</p>
      ]]></description>
    </item>
    <!-- 保留最近 30 天的 digest -->
  </channel>
</rss>
```

**数量不设上限：** 聚类出多少热点就展示多少，必读有几篇就展示几篇，值得关注的独立文章全部展示。每天约 100 篇输入，AI 过滤噪音后实际展示量会小于 100。

**历史保留：** feed.xml 保留最近 30 天的 digest 条目。

## File Structure

```
rss-feed-hub/
├── digest/
│   ├── Dockerfile          # Python 3.12 + supercronic
│   ├── crontab             # 0 8 * * * python /app/main.py
│   ├── requirements.txt    # anthropic, requests
│   ├── main.py             # 入口：拉文章 → AI 处理 → 生成 XML
│   ├── summarize.py        # Claude API 调用（Step 1 + Step 2）
│   ├── feed_builder.py     # RSS XML 生成
│   └── config.yaml         # 必读 feed 列表、摘要语言等配置
├── docker-compose.yml      # 新增 digest-worker + nginx
└── .env                    # 新增 ANTHROPIC_API_KEY, MINIFLUX_API_KEY
```

## Docker Compose Changes

```yaml
# 新增 services
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

# 新增 volume
volumes:
  miniflux-db:       # 已有
  digest-output:     # 新增
```

## Config

```yaml
# digest/config.yaml
must_read_feeds:
  - "Andrej Karpathy blog"

digest:
  schedule: "0 8 * * *"
  lookback_hours: 24
  history_days: 30
  summary_language: "zh-CN"

claude:
  model: "claude-haiku-4-5-20251001"
  max_article_length: 2000
  max_cluster_article_length: 500

miniflux:
  # URL and API key come from environment variables
  entries_per_page: 100
```

## Authentication

digest-worker 通过 Miniflux API Key 认证（比用户名密码更适合服务间调用）。

用户需要在 Miniflux 中生成 API Key：Settings → API Keys → Create API Key，然后将 key 添加到 `.env` 文件的 `MINIFLUX_API_KEY` 中。

## .env Changes

```
# 新增
ANTHROPIC_API_KEY=sk-ant-...
MINIFLUX_API_KEY=...
```
