---
name: scrapling
source: "D4Vinci/Scrapling (written from scratch)"
version: "1.0"
description: >
  Python web scraping library with anti-bot bypass, adaptive element tracking, Playwright integration, and MCP server. Triggers: /scrapling, web scraping, stealth scraping, Cloudflare bypass.
triggers: [scrapling, web scraping, stealth scraping, anti-bot bypass, Cloudflare bypass, adaptive scraping, playwright scraping, spider crawling, парсинг сайтов, обход защиты, веб-скрейпинг, Cloudflare обход]
tokens: ~2000
---

<!-- BSV
Скил   : scrapling
TL;DR  : Scrapling — Python 3.10+ библиотека для парсинга с обходом anti-bot и адаптивным трекингом элементов
Вызов  : /scrapling, web scraping, stealth scraping, Cloudflare bypass
НЕ для : парсинга сайтов, нарушающих ToS; замены Playwright напрямую (Scrapling оборачивает его)
-->

# Scrapling — Web Scraping with Anti-Bot Bypass

Python 3.10+ scraping library by D4Vinci. Key differentiator: **adaptive element tracking** — selectors auto-update when site layouts change. Supports stealth HTTP, full Playwright, multi-page Spider, and an MCP server.

---

## Installation

```bash
# Full install (all fetchers + dependencies)
pip install "scrapling[all]"

# Install browser binaries (required for StealthyFetcher and DynamicFetcher)
scrapling install

# MCP server support
pip install "scrapling[ai]"
```

Minimum: Python 3.10+. Browser install downloads Camoufox and Playwright chromium.

---

## Core Classes

| Class | Use Case | Anti-Bot | JS |
|-------|----------|----------|----|
| `Fetcher` | Fast HTTP, static pages | Basic | No |
| `StealthyFetcher` | Cloudflare, bot-protected sites | High | No |
| `DynamicFetcher` | JS-rendered, SPAs, interaction | High | Yes (Playwright) |
| `Spider` | Multi-page crawl | Depends on fetcher | Optional |
| `ProxyRotator` | Rotate proxies across requests | — | — |

Async variants: `AsyncStealthySession`, `AsyncDynamicSession`

---

## Fetcher — Fast HTTP

Best for: static HTML pages, APIs without bot protection.

```python
from scrapling import Fetcher

fetcher = Fetcher(auto_match=True)
page = fetcher.get("https://example.com/products")

# CSS selector with ::text pseudo-element
titles = page.css("h2.product-title::text")          # returns list of strings
first_title = page.css_first("h2.product-title::text")

# CSS with ::attr() for attributes
links = page.css("a.product-link::attr(href)")

# XPath
prices = page.xpath("//span[@class='price']/text()")

# Adaptive element — survives layout changes
price_elem = page.find("span.price", auto_match=True)
price_elem.save()   # saves fingerprint to local DB for future sessions
```

### POST / custom headers

```python
page = fetcher.post(
    "https://api.example.com/search",
    json={"query": "scrapling"},
    headers={"Authorization": "Bearer TOKEN"},
)
data = page.json()   # parsed JSON response
```

---

## StealthyFetcher — Cloudflare Bypass

Uses Camoufox for browser fingerprint spoofing. Bypasses Cloudflare, Datadome, PerimeterX.

```python
from scrapling import StealthyFetcher

# Synchronous context manager
with StealthyFetcher() as fetcher:
    page = fetcher.fetch("https://cloudflare-protected-site.com")
    emails = page.css("a[href^='mailto:']::attr(href)")

# With proxy
with StealthyFetcher(proxy="http://user:pass@proxy:8080") as fetcher:
    page = fetcher.fetch("https://target.com")
```

### Async variant

```python
import asyncio
from scrapling import AsyncStealthySession

async def scrape():
    async with AsyncStealthySession() as session:
        page = await session.fetch("https://target.com")
        return page.css("h1::text")

result = asyncio.run(scrape())
```

---

## DynamicFetcher — Full Playwright

For JavaScript-rendered pages, SPAs, click interactions, form fills.

```python
from scrapling import DynamicFetcher

with DynamicFetcher() as fetcher:
    page = fetcher.fetch(
        "https://spa-app.com",
        wait_selector=".product-grid",   # wait for element before parsing
        wait_timeout=10_000,             # ms
    )
    products = page.css(".product-card")
    for p in products:
        print(p.css_first("h3::text"), p.css_first(".price::text"))
```

### Interact with the page (click, scroll, fill)

```python
with DynamicFetcher() as fetcher:
    page = fetcher.fetch("https://example.com/login")
    page.find("input#email").fill("user@example.com")
    page.find("input#password").fill("password")
    page.find("button[type=submit]").click()
    page.wait_for_selector(".dashboard", timeout=5000)
    dashboard_html = page.content
```

### Async variant

```python
from scrapling import AsyncDynamicSession

async def scrape_spa():
    async with AsyncDynamicSession() as session:
        page = await session.fetch("https://spa-app.com", wait_selector=".data")
        return page.css(".data-row::text")
```

---

## Spider — Multi-Page Crawling

```python
from scrapling import Spider, Fetcher

spider = Spider(
    start_urls=["https://news-site.com"],
    fetcher=Fetcher(),                   # or StealthyFetcher() for protected sites
    concurrent_requests=5,
    follow_robots_txt=True,
    max_pages=200,
)

@spider.on_response
def parse(page):
    articles = page.css("article.post")
    for article in articles:
        yield {
            "title": article.css_first("h2::text"),
            "url": article.css_first("a::attr(href)"),
            "date": article.css_first("time::attr(datetime)"),
        }
    # Follow pagination
    next_page = page.css_first("a.next-page::attr(href)")
    if next_page:
        yield spider.follow(next_page)

# Stream results as they arrive
for item in spider.crawl(stream=True):
    print(item)

# Pause and resume (state saved to disk)
spider.pause()
# ... later ...
spider.resume()
```

---

## CSS Selector Patterns

Scrapling extends standard CSS selectors with pseudo-elements:

```python
# ::text — extract text content
page.css("h1::text")                    # ["Page Title"]
page.css("p::text")                     # all paragraph texts

# ::attr(name) — extract attribute value
page.css("img::attr(src)")              # all image sources
page.css("a::attr(href)")               # all link hrefs
page.css("input::attr(placeholder)")    # all input placeholders

# Combined: nested text
page.css("div.card > h3::text")

# First match only
page.css_first("meta[name=description]::attr(content)")

# XPath (full support)
page.xpath("//div[@class='price']/text()")
page.xpath("//a/@href")

# Adaptive element (fingerprinted, survives layout changes)
elem = page.find("div.price", auto_match=True)
elem.save()   # persist fingerprint
# Future runs: elem re-found even if class changes to "cost" or "amount"
```

---

## ProxyRotator

```python
from scrapling import ProxyRotator, Fetcher

proxies = ProxyRotator([
    "http://user1:pass1@proxy1:8080",
    "http://user2:pass2@proxy2:8080",
    "socks5://user3:pass3@proxy3:1080",
])

fetcher = Fetcher(proxy_rotator=proxies)
# Each request uses the next proxy in rotation (round-robin by default)
page = fetcher.get("https://target.com")
```

---

## MCP Server Setup

Expose Scrapling as an MCP tool for Claude or other LLM agents:

```bash
pip install "scrapling[ai]"
```

Add to your MCP config (e.g., `~/.claude/mcp.json`):

```json
{
  "mcpServers": {
    "scrapling": {
      "command": "python",
      "args": ["-m", "scrapling.mcp"],
      "env": {}
    }
  }
}
```

Available MCP tools after connection:
- `scrapling_fetch` — fast HTTP fetch + CSS/XPath query
- `scrapling_stealth_fetch` — stealth fetch (Cloudflare bypass)
- `scrapling_dynamic_fetch` — Playwright fetch with JS execution
- `scrapling_spider` — crawl multiple pages

---

## Adaptive Element Tracking — How It Works

Standard scrapers break when a site redesigns. Scrapling stores element **fingerprints** (text content, surrounding structure, visual position, computed styles) in a local SQLite DB. On future runs, it uses these fingerprints to re-locate elements even if class names, IDs, or DOM structure changed.

```python
# First run: save fingerprint
page = fetcher.get("https://shop.com/product/123")
price = page.find("span.price", auto_match=True)
price.save(label="product_price")

# After site redesign (class changed from .price to .product-cost):
price = page.find_saved("product_price")   # still finds it
```

Enable globally: `Fetcher(auto_match=True)` — all finds are adaptive by default.

---

## Common Patterns

### Scrape paginated list
```python
from scrapling import Fetcher

fetcher = Fetcher()
results = []

for page_num in range(1, 11):
    page = fetcher.get(f"https://example.com/items?page={page_num}")
    items = page.css("li.item")
    if not items:
        break
    for item in items:
        results.append({
            "name": item.css_first(".name::text"),
            "price": item.css_first(".price::text"),
        })
```

### Scrape protected site (Cloudflare)
```python
from scrapling import StealthyFetcher

with StealthyFetcher(headless=True) as f:
    page = f.fetch("https://protected-site.com/data")
    rows = page.css("table.results tr")
    data = [
        [cell.css_first("::text") for cell in row.css("td")]
        for row in rows[1:]   # skip header row
    ]
```

### Async batch scraping
```python
import asyncio
from scrapling import AsyncStealthySession

URLS = ["https://site.com/a", "https://site.com/b", "https://site.com/c"]

async def scrape_all():
    async with AsyncStealthySession() as session:
        pages = await asyncio.gather(*[session.fetch(url) for url in URLS])
        return [p.css_first("h1::text") for p in pages]

titles = asyncio.run(scrape_all())
```

---

## Quick Reference

```
pip install "scrapling[all]" && scrapling install

Fetcher()            — fast HTTP, no JS
StealthyFetcher()    — anti-bot, Cloudflare bypass, no JS
DynamicFetcher()     — Playwright, full JS, interaction
Spider()             — multi-page, pause/resume, streaming
ProxyRotator([...])  — round-robin proxy rotation

.css("sel::text")         — list of text strings
.css_first("sel::text")   — first match string
.css("sel::attr(href)")   — list of attribute values
.xpath("//x/text()")      — XPath text extraction
.find("sel", auto_match=True)  — adaptive element
```
