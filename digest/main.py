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

    try:
        articles = fetch_entries(base_url, api_key, config["digest"]["lookback_hours"])
    except Exception as e:
        print(f"Failed to fetch entries: {e}")
        return

    if not articles:
        print("No articles found, skipping digest generation.")
        return

    print(f"Fetched {len(articles)} articles")

    max_articles = config["digest"].get("max_articles", 200)
    if len(articles) > max_articles:
        articles = articles[:max_articles]
        print(f"Trimmed to {len(articles)} most recent articles")

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

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml)

    topic_count = len(digest["hot_topics"])
    must_read_count = len(digest["must_read"])
    notable_count = sum(len(v) for v in digest["notable"].values())
    print(f"Digest generated: {topic_count} topics, {must_read_count} must-read, {notable_count} notable")


if __name__ == "__main__":
    run_digest()
