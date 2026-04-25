# 科研代理搜索服务 - ProxySearch

## 概述

专为科研场景设计的低频代理搜索服务，解决"源不可靠、存活期短"的痛点。

## 核心设计理念

1. **社区维护 > 自己爬取**：使用 proxyscrape 等聚合 API
2. **验证闭环**：抓取 → 验证 → 使用 → 淘汰
3. **科研友好**：低频使用、开源透明、伦理合规

## 架构

```
proxy_search/
├── __init__.py            # 模块入口
├── proxy_sources.py       # 代理源管理（聚合API）
├── validator.py           # 多级验证器
├── proxy_pool.py          # 代理池管理
├── proxy_middleware.py    # 请求中间件
└── config.py              # 配置
```

## 数据源

| 源 | 类型 | URL | 特点 |
|----|------|-----|------|
| proxyscrape | API | api.proxyscrape.com | HTTP/SOCKS4/SOCKS5，更新频繁 |
| free-proxy-list | API | free-proxy-list.net | 经典源，HTTP 为主 |
| proxys.herokuapp | API | proxys.herokuapp.com | 社区聚合，质量较高 |

## 验证层级

| 层级 | 目标 | 超时 | 淘汰条件 |
|------|------|------|----------|
| L1 | 基础连通性 | 5s | 无法连接 httpbin |
| L2 | 匿名性检查 | 5s | 返回 IP 与代理 IP 不一致 |
| L3 | 目标站点兼容 | 10s | SSL 错误、状态码非 200/301/302 |

## 代理池策略

- **刷新频率**：每小时自动刷新
- **最小池大小**：5 个可用代理
- **使用策略**：随机选取 + 失败重试 2 次
- **淘汰机制**：连续失败 3 次移除

## 伦理合规

- User-Agent 标注科研用途
- 严格遵守 Rate Limiting
- 仅用于学术研究目的
