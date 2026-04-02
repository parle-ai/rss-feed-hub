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
