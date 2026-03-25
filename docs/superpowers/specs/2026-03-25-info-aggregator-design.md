# Info Aggregator Dashboard — Design Spec

## Overview

Self-hosted information aggregator using RSSHub + Miniflux + PostgreSQL, deployed locally via Docker Compose. Aggregates B站 UP 主视频更新和小红书用户笔记到一个统一的阅读界面。

## Goals

- 在一个 Dashboard 里看到 B站和小红书的订阅更新
- 本地 Docker 一键部署，零云依赖
- 可扩展：后续可随时添加 YouTube、X、HN 等信息源

## Non-Goals

- 自定义前端（Phase 1 使用 Miniflux 自带 UI）
- AI 摘要/翻译（后续考虑）
- 多用户支持（单人使用）

## Architecture

```
┌──────────────┐     RSS      ┌──────────────┐     ┌──────────────┐
│    RSSHub    │─────────────▶│   Miniflux   │────▶│  PostgreSQL  │
│  port: 1200  │              │  port: 8080  │     │  port: 5432  │
└──────────────┘              └──────────────┘     └──────────────┘
```

三个 Docker 容器，通过 Docker 内部网络通信。用户通过 `http://localhost:8080` 访问 Miniflux Web UI。

## Components

### 1. RSSHub (信息源转换层)

- **Image:** `diygod/rsshub:chromium-bundled` (需要 Chromium 支持小红书的 Puppeteer 渲染)
- **Port:** 1200
- **作用:** 将 B站、小红书等平台内容转为标准 RSS feed
- **路由:**
  - B站 UP 主视频: `http://rsshub:1200/bilibili/user/video/{uid}` (uid 从 UP 主主页 URL 获取，不需要 Puppeteer)
  - 小红书用户笔记: `http://rsshub:1200/xiaohongshu/user/{user_id}/notes` (user_id 是 24 位字符串，**需要 Puppeteer**)
- **配置:**
  - `NODE_ENV=production`
  - `CACHE_TYPE=memory` (本地部署够用)
  - `PUPPETEER_WS_ENDPOINT` — 如果使用外置 Chromium 容器则需配置
  - 可选: `BILIBILI_COOKIE` — B站登录 cookie，减少 412 错误
  - **必须:** `XIAOHONGSHU_COOKIE` — 小红书 cookie，反爬需要，不配基本不能用
- **注意:**
  - 小红书路由依赖 Puppeteer 无头浏览器渲染，必须用 `chromium-bundled` 镜像或单独部署 Chromium
  - 小红书反爬非常激进，历史上多次因反爬升级导致路由失效（#8905, #12365, #16300），需要有心理准备
  - B站可能返回 HTTP 412，配置 cookie 可缓解

### 2. Miniflux (聚合 + 阅读层)

- **Image:** `miniflux/miniflux:latest`
- **Port:** 8080
- **作用:** 订阅 RSSHub 生成的 RSS 链接，定时抓取，提供 Web UI 阅读
- **配置:** 所有敏感值通过 `.env` 文件注入
  - `DATABASE_URL` — 连接 PostgreSQL（密码来自 `${DB_PASSWORD}`）
  - `RUN_MIGRATIONS=1`
  - `CREATE_ADMIN=1`
  - `ADMIN_USERNAME` / `ADMIN_PASSWORD` — 来自 `.env`
  - `POLLING_FREQUENCY=15` — 每 15 分钟调度一批 feed 刷新（非所有 feed 同时刷新）

### 3. PostgreSQL (数据存储)

- **Image:** `postgres:16-alpine`
- **Port:** 5432 (仅内部访问，不暴露到宿主机)
- **配置:** 密码通过 `.env` 的 `${DB_PASSWORD}` 注入
- **持久化:** Docker volume `miniflux-db`

## File Structure

```
project/
├── docker-compose.yml      # 三个服务的编排
├── .env                    # 密码等敏感配置
├── .env.example            # 配置模板（不含真实密码）
├── .gitignore              # 忽略 .env
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-03-25-info-aggregator-design.md
```

## Docker Compose 结构

```yaml
services:
  rsshub:
    image: diygod/rsshub:chromium-bundled
    ports:
      - "1200:1200"    # 可选：仅调试用，生产可移除
    environment:
      - NODE_ENV=production
      - CACHE_TYPE=memory
      - BILIBILI_COOKIE=${BILIBILI_COOKIE:-}
      - XIAOHONGSHU_COOKIE=${XIAOHONGSHU_COOKIE:-}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:1200/"]
      interval: 30s
      timeout: 10s
      retries: 3

  miniflux:
    image: miniflux/miniflux:latest
    ports:
      - "8080:8080"
    depends_on:
      db:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgres://miniflux:${DB_PASSWORD}@db/miniflux?sslmode=disable
      - RUN_MIGRATIONS=1
      - CREATE_ADMIN=1
      - ADMIN_USERNAME=${ADMIN_USERNAME}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - POLLING_FREQUENCY=15
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=miniflux
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=miniflux
    volumes:
      - miniflux-db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "miniflux"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

volumes:
  miniflux-db:
```

## .env.example

```
# Database
DB_PASSWORD=changeme

# Miniflux admin
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme

# RSSHub cookies (可选，小红书强烈建议配置)
BILIBILI_COOKIE=
XIAOHONGSHU_COOKIE=
```

## 使用流程

1. 复制 `.env.example` 为 `.env`，填入密码和 cookie
2. `docker compose up -d` 启动所有服务
3. 访问 `http://localhost:8080`，用 admin 账号登录 Miniflux
4. 添加订阅（在 Miniflux 里填入以下 URL，`rsshub` 是 Docker 内部域名）：
   - B站 UP 主: `http://rsshub:1200/bilibili/user/video/{uid}`
   - 小红书用户: `http://rsshub:1200/xiaohongshu/user/{user_id}/notes`
   - 浏览器测试用 `localhost:1200` 替代 `rsshub:1200`
5. Miniflux 自动定时抓取，打开即看

## 扩展路径

后续想加更多信息源，只需在 Miniflux 里添加新的 RSSHub 订阅：

| 平台 | RSSHub 路由示例 |
|---|---|
| YouTube 频道 | `http://rsshub:1200/youtube/channel/{id}` |
| X/Twitter 用户 | `http://rsshub:1200/twitter/user/{username}` |
| Hacker News 首页 | `http://rsshub:1200/hackernews/best` |
| Reddit 子版块 | `http://rsshub:1200/reddit/subreddit/{name}` |
| 微博用户 | `http://rsshub:1200/weibo/user/{uid}` |

## 已知限制

- 小红书反爬较严，RSSHub 路由可能不稳定，需要配置 cookie
- B站部分内容需要登录 cookie 才能获取完整信息
- Miniflux 自带 UI 功能完整但外观朴素，后续可考虑自定义前端
