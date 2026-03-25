# RSS Feed Hub

> **Open, hackable, yours.** — Inspired by [Andrej Karpathy's call to bring back RSS](https://x.com/karpathy/status/2018043254986703167).

A self-hosted information aggregator that pulls content from platforms that don't want you to leave their app — and puts it all in one place you control.

No algorithms deciding what you see. No ads. No tracking. Just your subscriptions, in chronological order, on your own machine.

## Philosophy

The internet was built on open protocols. RSS is one of them — a simple, universal way for any website to say "here's what's new." But platforms killed it. They want you doom-scrolling their feed, not reading on your terms.

This project fights back:

- **Open** — Built entirely on open-source software and open protocols (RSS/Atom)
- **Hackable** — Everything is a config file, an API call, or a Docker container. Fork it, extend it, make it yours
- **Self-hosted** — Your data lives on your machine. No cloud dependency, no account required, no one can shut it down
- **Platform-agnostic** — Bilibili, YouTube, Hacker News, WSJ — they all become the same thing: a feed

## What's Inside

```
┌──────────────┐     RSS      ┌──────────────┐     ┌──────────────┐
│    RSSHub    │─────────────▶│   Miniflux   │────▶│  PostgreSQL  │
│  万物皆可RSS  │              │  阅读 + API   │     │   数据持久化  │
└──────────────┘              └──────────────┘     └──────────────┘
       ▲                             │
  B站 / YouTube                      ▼
  HN / Reddit               NetNewsWire / Reeder
  News / Blogs               (or any RSS client)
```

| Component | Role | Port |
|-----------|------|------|
| [RSSHub](https://github.com/DIYgod/RSSHub) | Turns "everything" into RSS — Bilibili, YouTube, Reddit, and 1000+ more | 1200 |
| [Miniflux](https://github.com/miniflux/v2) | Minimal, fast RSS reader with a full REST API | 8080 |
| PostgreSQL | Stores your feeds, articles, and read state | 5432 (internal) |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/parle-ai/rss-feed-hub.git
cd rss-feed-hub

# 2. Configure
cp .env.example .env
# Edit .env — set passwords and cookies

# 3. Run
docker compose up -d

# 4. Open
open http://localhost:8080
```

## Current Feeds

| Category | Sources |
|----------|---------|
| **B站** | Your Bilibili followings (via RSSHub) |
| **YouTube** | 52 subscribed channels (native RSS) |
| **News** | Hacker News, Ars Technica, MIT News, OpenAI, Bloomberg, WSJ, CNBC, and more |
| **Karpathy HN Top Blogs** | 91 most popular blogs from Hacker News 2025 |

## Native Client Support

Miniflux exposes a Google Reader-compatible API. Connect any client:

**NetNewsWire (recommended):**
1. Settings → Accounts → Add → FreshRSS
2. API URL: `http://localhost:8080` (no trailing slash)
3. Use your Google Reader credentials (set in Miniflux → Settings → Integrations)

Also works with: Reeder, lire, News Explorer, FeedMe, and [more](https://miniflux.app/docs/apps.html).

## Adding More Feeds

```bash
# Any website with native RSS — add directly in Miniflux UI or API
curl -X POST http://localhost:8080/v1/feeds \
  -u admin:yourpassword \
  -H "Content-Type: application/json" \
  -d '{"feed_url":"https://example.com/feed.xml","category_id":1}'

# Websites without RSS — use RSSHub routes
# Full route list: https://docs.rsshub.app
# Example: http://rsshub:1200/twitter/user/karpathy
```

## Roadmap

- [ ] AI-powered article summarization (local LLM via Ollama)
- [ ] Custom frontend dashboard (React/Next.js on Miniflux API)
- [ ] Xiaohongshu integration (RSSHub route currently unstable, may need custom scraper)
- [ ] Mobile push notifications for high-priority feeds

## Docs

- [How It Works](docs/how-it-works.md) — Visual guide to RSS, RSSHub, Docker, and how they fit together
- [Design Spec](docs/superpowers/specs/2026-03-25-info-aggregator-design.md) — Architecture decisions
- [Implementation Plan](docs/superpowers/plans/2026-03-25-info-aggregator.md) — Step-by-step build log

## Why RSS?

> "Finding myself going back to RSS/Atom feeds a lot more recently. There's a lot more higher quality longform and a lot less slop intended to provoke."
> — Andrej Karpathy

RSS is:
- **Chronological** — no algorithm reordering your feed
- **Private** — no one tracks what you read
- **Portable** — switch readers anytime, your subscriptions come with you (OPML)
- **Resilient** — works offline, no account needed, can't be enshittified

## License

MIT
