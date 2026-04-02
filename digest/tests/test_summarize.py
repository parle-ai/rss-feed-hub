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


from summarize import generate_digest_summaries

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
