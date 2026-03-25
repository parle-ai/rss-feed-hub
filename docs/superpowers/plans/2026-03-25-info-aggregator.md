# Info Aggregator (RSSHub + Miniflux) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a self-hosted RSSHub + Miniflux stack via Docker Compose on the local Mac, capable of aggregating B站 and 小红书 feeds into a unified reader.

**Architecture:** Three Docker containers (RSSHub, Miniflux, PostgreSQL) orchestrated by Docker Compose. RSSHub converts social media content to RSS feeds; Miniflux subscribes to those feeds and provides the reading UI. All config via `.env` file.

**Tech Stack:** Docker Compose, RSSHub (chromium-bundled image), Miniflux, PostgreSQL 16

**Spec:** `docs/superpowers/specs/2026-03-25-info-aggregator-design.md`

**Prerequisites:** Docker Desktop installed and running. Verify with `docker compose version`.

**Troubleshooting:** If any service fails to start, check logs with `docker compose logs <service>`. To start fresh (e.g., wrong password), run `docker compose down -v` to wipe volumes — note that `CREATE_ADMIN=1` only creates the admin on first run, so changing the admin password requires wiping the DB volume.

---

### Task 1: Initialize Git Repo and Project Skeleton

**Files:**
- Create: `.gitignore`
- Create: `.env.example`

- [ ] **Step 1: Initialize git repo**

Run: `git init`

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.env
.superpowers/
```

- [ ] **Step 3: Create `.env.example`**

```env
# Database
DB_PASSWORD=changeme

# Miniflux admin
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme

# RSSHub cookies (小红书必须配置，B站建议配置)
BILIBILI_COOKIE=
XIAOHONGSHU_COOKIE=
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.example
git commit -m "init: project skeleton with .gitignore and .env.example"
```

---

### Task 2: Create Docker Compose Configuration

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  rsshub:
    image: diygod/rsshub:chromium-bundled
    ports:
      - "1200:1200"
    environment:
      - NODE_ENV=production
      - CACHE_TYPE=memory
      - BILIBILI_COOKIE=${BILIBILI_COOKIE:-}
      - XIAOHONGSHU_COOKIE=${XIAOHONGSHU_COOKIE:-}
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:1200/ || exit 1"]
      interval: 30s
      start_period: 60s
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
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthcheck"]
      interval: 30s
      timeout: 10s
      retries: 3
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

- [ ] **Step 2: Validate compose file syntax**

Run: `docker compose config --quiet`
Expected: No output (means valid)

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose with RSSHub, Miniflux, and PostgreSQL"
```

---

### Task 3: Create `.env` and Start Services

**Files:**
- Create: `.env` (from `.env.example`, not committed)

- [ ] **Step 1: Create `.env` from template**

```bash
cp .env.example .env
```

Then edit `.env` — generate real passwords (e.g., `openssl rand -base64 16`) and fill in `DB_PASSWORD` and `ADMIN_PASSWORD`. Leave cookie fields empty for now (B站 can work without it; 小红书 needs it but we'll verify the stack first).

- [ ] **Step 2: Pull images**

Run: `docker compose pull`
Expected: All three images download successfully. Note: `chromium-bundled` image is ~1GB+.

- [ ] **Step 3: Start all services**

Run: `docker compose up -d`
Expected: Three containers start.

- [ ] **Step 4: Verify all containers are healthy**

Run: `docker compose ps`
Expected: All three services show `Up` status. `db` should show `healthy`. RSSHub healthcheck may take 30s.

- [ ] **Step 5: Verify RSSHub is responding**

Run: `curl -s http://localhost:1200/ | head -20`
Expected: HTML response from RSSHub homepage.

- [ ] **Step 6: Verify Miniflux is responding**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/`
Expected: `200` or `302` (redirect to login).

---

### Task 4: Verify B站 Feed via RSSHub

- [ ] **Step 1: Test B站 route with a known UP主**

Pick a popular UP主 UID for testing (e.g., `546195` for 老番茄).

Run: `curl -s "http://localhost:1200/bilibili/user/video/546195" | head -30`
Expected: Valid XML/RSS output containing `<item>` entries with video titles.

- [ ] **Step 2: If 412 error, configure BILIBILI_COOKIE**

If the response contains an error or is empty:
1. Open Bilibili in browser, log in
2. Open DevTools → Network → copy `Cookie` header value
3. Add to `.env`: `BILIBILI_COOKIE=your_cookie_here`
4. Run: `docker compose up -d rsshub` (restart RSSHub)
5. Re-test the curl command

---

### Task 5: Verify 小红书 Feed via RSSHub

- [ ] **Step 1: Test 小红书 route (will likely fail without cookie)**

Run: `curl -s "http://localhost:1200/xiaohongshu/user/593032945e87e77791e03696/notes" | head -30`
Expected: Likely an error or empty response without cookie.

- [ ] **Step 2: Configure XIAOHONGSHU_COOKIE**

1. Open 小红书 web (xiaohongshu.com) in browser, log in
2. Open DevTools → Network → any request → copy `Cookie` header value
3. Add to `.env`: `XIAOHONGSHU_COOKIE=your_cookie_here`
4. Run: `docker compose up -d rsshub` (restart RSSHub)

- [ ] **Step 3: Re-test with cookie**

Run: `curl -s "http://localhost:1200/xiaohongshu/user/593032945e87e77791e03696/notes" | head -30`
Expected: Valid RSS XML with `<item>` entries. If still failing, this is a known RSSHub stability issue — check https://github.com/DIYgod/RSSHub/issues for current status.

---

### Task 6: Add Subscriptions in Miniflux

- [ ] **Step 1: Log in to Miniflux**

Open `http://localhost:8080` in browser. Log in with the `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.

- [ ] **Step 2: Create categories**

In Miniflux UI: Settings → Categories → add two categories:
- `B站`
- `小红书`

- [ ] **Step 3: Subscribe to B站 UP主**

In Miniflux UI: Subscriptions → Add → enter URL:
```
http://rsshub:1200/bilibili/user/video/{your_up_uid}
```
Assign to category `B站`. Replace `{your_up_uid}` with the actual UID.

- [ ] **Step 4: Subscribe to 小红书用户**

In Miniflux UI: Subscriptions → Add → enter URL:
```
http://rsshub:1200/xiaohongshu/user/{your_user_id}/notes
```
Assign to category `小红书`. Replace `{your_user_id}` with the actual 24-char user ID.

- [ ] **Step 5: Trigger manual refresh and verify**

In Miniflux UI: Subscriptions → click each feed → Refresh. Verify articles appear in the Unread view.

---

### Task 7: Commit Docs and Final Verification

- [ ] **Step 1: Commit spec and plan docs**

```bash
git add docs/
git commit -m "docs: add design spec and implementation plan"
```

- [ ] **Step 2: Final smoke test**

Verify the full stack:
1. `docker compose ps` — all 3 healthy
2. `http://localhost:8080` — Miniflux shows articles from B站/小红书
3. `http://localhost:1200` — RSSHub homepage accessible

- [ ] **Step 3: Done!**

The stack is running. To stop: `docker compose down`. To restart: `docker compose up -d`. Data persists in the `miniflux-db` volume.
