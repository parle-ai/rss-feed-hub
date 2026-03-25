# 原理图解：RSS + RSSHub + Docker + Miniflux + NetNewsWire

## 一、什么是 RSS？

想象**报纸订阅**：

```
没有 RSS 的世界：

  B站      YouTube     知乎       HN
   │          │          │         │
   ▼          ▼          ▼         ▼
  你每天要打开 4 个网站，一个一个翻，看有没有更新
```

**RSS** 就像一个统一的"邮箱"。每个网站把更新打包成一种标准格式（XML），
你用一个阅读器订阅，新内容自动送到你面前：

```mermaid
graph TD
    A[B站] -->|RSS| R[RSS 阅读器<br/>Miniflux]
    B[YouTube] -->|RSS| R
    C[知乎] -->|RSS| R
    D[Hacker News] -->|RSS| R
    R --> U[你：一个地方看所有更新]
```

RSS 本质就是一个**标准化的更新通知协议**。
就像 email 不管你用 Gmail 还是 Outlook 都能收发，RSS 不管哪个网站，格式都一样。

---

## 二、问题：很多网站不提供 RSS

B站、小红书、微博……这些平台**故意不给你 RSS**，因为它们要你打开 App 看广告。

这就是 **RSSHub** 解决的问题：

```mermaid
graph LR
    A[B站<br/>没有 RSS] --> R[RSSHub<br/>翻译官]
    B[小红书<br/>没有 RSS] --> R
    R -->|标准 RSS 格式| M[Miniflux<br/>阅读器]
```

**RSSHub 就是一个"翻译官"** — 它模拟浏览器去访问 B站/小红书，
把页面内容抓下来，翻译成标准 RSS 格式。这样 Miniflux 就能订阅了。

---

## 三、什么是 Docker？

你装一个软件，通常要操心：装什么版本的数据库？环境变量怎么配？
会不会跟我电脑上其他东西冲突？

**Docker 就是"软件的集装箱"：**

```mermaid
graph TB
    subgraph Mac["你的 Mac"]
        subgraph Docker["Docker (OrbStack)"]
            C1["容器1: RSSHub<br/>自带 Node.js + Chromium"]
            C2["容器2: Miniflux<br/>自带 Go 运行时"]
            C3["容器3: PostgreSQL<br/>自带数据库引擎"]
        end
    end

    style Docker fill:#e8f4f8,stroke:#2196F3
    style Mac fill:#f5f5f5,stroke:#999
```

每个容器是一个隔离的小世界，里面自带运行所需的一切。
**Docker Compose** 则是"编排工具" — 用一个 `docker-compose.yml` 文件
定义"我要 3 个容器，它们怎么连接"，然后 `docker compose up` 一键全部启动。

---

## 四、客户端：NetNewsWire

Miniflux 自带 Web UI（localhost:8080），但外观朴素。
**NetNewsWire** 是一个开源的 macOS/iOS 原生 RSS 客户端，颜值更高。

它不是替代 Miniflux，而是另一个**入口**：

```mermaid
graph TD
    M[Miniflux<br/>后端 + 数据存储<br/>localhost:8080]
    NNW[NetNewsWire<br/>macOS 原生客户端]
    WEB[浏览器<br/>localhost:8080]

    NNW -->|Google Reader API| M
    WEB -->|Web UI| M
    M --> DB[(PostgreSQL)]
```

**NetNewsWire 是纯客户端**，它不存数据、不抓 feed。所有数据存在 Miniflux + PostgreSQL 里。
NetNewsWire 通过 Google Reader API 跟 Miniflux 对话（拉文章、同步已读状态、管理订阅）。

类比：Miniflux 是**邮件服务器**（Gmail 后台），NetNewsWire 是**邮件客户端**（Outlook app）。
你可以同时用多个客户端，数据自动同步。

---

## 五、完整数据流

```mermaid
sequenceDiagram
    participant B as B站
    participant R as RSSHub<br/>(localhost:1200)
    participant M as Miniflux<br/>(localhost:8080)
    participant DB as PostgreSQL
    participant U as 你（Web UI 或 NetNewsWire）

    loop 每 15 分钟
        M->>R: 有新内容吗？
        R->>B: 模拟浏览器访问 B站 API
        B-->>R: 返回 UP 主最新动态
        R-->>M: 翻译成 RSS XML 返回
        M->>DB: 存储新文章
    end

    U->>M: 打开 Miniflux（Web 或 NetNewsWire）
    M->>DB: 读取未读文章
    DB-->>M: 返回文章列表
    M-->>U: 展示所有更新
    U->>M: 标记已读
    M->>DB: 更新状态（所有客户端自动同步）
```

---

## 六、一句话总结

| 组件 | 角色 | 类比 |
|------|------|------|
| **RSS** | 标准更新格式 | 信件格式（信封+地址+内容） |
| **RSSHub** | 把不支持 RSS 的网站转成 RSS | 翻译官 / 代购 |
| **Miniflux** | RSS 阅读器 + 数据库 | 你的统一邮箱 |
| **Docker** | 让软件互不干扰地运行 | 集装箱：每个软件住自己的箱子 |
| **Docker Compose** | 一键编排多个容器 | 集装箱调度表 |
| **OrbStack** | macOS 上的 Docker 引擎 | 码头（让集装箱能跑起来） |
| **NetNewsWire** | macOS/iOS 原生 RSS 客户端 | 邮件客户端（Outlook），连着邮件服务器（Miniflux）用 |
