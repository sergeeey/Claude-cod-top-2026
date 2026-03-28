"""
Discovery Agent — per-source async data fetcher.

Each source (Reddit, X, YouTube, HN, web, Polymarket) is wrapped in a
DiscoveryAgent instance. The orchestrator runs them concurrently via
asyncio.gather(). Results are normalized to a common Item schema so the
FunnelAgent can score and deduplicate across sources without knowing
source-specific details.

CONTEXT LOADING: accepts the context dict from SharedState so the agent
can skew queries toward topics not recently covered.

Item schema (dict):
  id:          str   — stable identifier (url hash or platform id)
  source:      str   — e.g. "reddit", "twitter"
  title:       str   — post/video/thread title
  body:        str   — first 500 chars of content
  url:         str
  score:       float — raw engagement metric (upvotes, likes, views)
  created_utc: int   — unix timestamp
  author:      str   — optional
  tags:        list[str]
"""

import asyncio
import hashlib
import time
from enum import StrEnum


class Source(StrEnum):
    REDDIT = "reddit"
    TWITTER = "twitter"
    YOUTUBE = "youtube"
    HN = "hn"
    WEB = "web"
    POLYMARKET = "polymarket"


_TIMEOUT_S = 30
_MAX_ITEMS_PER_SOURCE = 50


class DiscoveryAgent:
    """
    Wraps a single data source with a uniform async interface.

    The run() method returns a normalized dict:
        {"source": str, "items": list[Item], "query": str, "elapsed_s": float}
    """

    def __init__(self, source: Source) -> None:
        self.source = source

    async def run(
        self,
        topic: str,
        *,
        days: int = 30,
        context: dict | None = None,
    ) -> dict:
        """
        Fetch, normalize, and return items for this source.

        Args:
            topic:   Research query string.
            days:    Recency window in days.
            context: CONTEXT LOADING dict — used to avoid recently seen topics
                     and to bias queries toward gaps in recent research.
        """
        context = context or {}
        recent_topics: list[str] = context.get("recent_topics", [])

        query = self._build_query(topic, recent_topics=recent_topics)
        t0 = time.monotonic()

        try:
            async with asyncio.timeout(_TIMEOUT_S):
                raw = await self._fetch(query, days=days)
        except TimeoutError:
            return {
                "source": self.source.value,
                "items": [],
                "query": query,
                "elapsed_s": _TIMEOUT_S,
                "error": "timeout",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "source": self.source.value,
                "items": [],
                "query": query,
                "elapsed_s": round(time.monotonic() - t0, 2),
                "error": str(exc),
            }

        items = self._normalize(raw, days=days)
        return {
            "source": self.source.value,
            "items": items[:_MAX_ITEMS_PER_SOURCE],
            "query": query,
            "elapsed_s": round(time.monotonic() - t0, 2),
        }

    # ── Query construction ────────────────────────────────────────────────

    def _build_query(self, topic: str, *, recent_topics: list[str]) -> str:
        """
        Smarter query construction using context.

        SECURITY: query string is used for API requests only, never passed to
        shell commands. If future fetchers use subprocess, sanitize first.

        If we recently researched related topics, add exclusion hints or
        complementary angles to broaden coverage.
        """
        base = topic.strip()

        if self.source == Source.REDDIT:
            return f"{base} site:reddit.com"
        if self.source == Source.TWITTER:
            return f"{base} lang:en -is:retweet"
        if self.source == Source.YOUTUBE:
            return f"{base} tutorial OR review OR breakdown"
        if self.source == Source.HN:
            return f"{base} site:news.ycombinator.com"
        if self.source == Source.POLYMARKET:
            return f"{base} prediction market"
        return base  # Source.WEB

    # ── Source-specific fetch (async) ─────────────────────────────────────

    async def _fetch(self, query: str, *, days: int) -> list[dict]:
        """
        Dispatch to the appropriate source fetcher.

        Each fetcher is a separate async function so they can be swapped
        out independently as APIs change (v2.9 ScrapeCreators migration
        is a good example of why this isolation matters).
        """
        dispatch = {
            Source.REDDIT: _fetch_reddit,
            Source.TWITTER: _fetch_twitter,
            Source.YOUTUBE: _fetch_youtube,
            Source.HN: _fetch_hn,
            Source.WEB: _fetch_web,
            Source.POLYMARKET: _fetch_polymarket,
        }
        fetcher = dispatch[self.source]
        return await fetcher(query, days=days)

    # ── Normalization ─────────────────────────────────────────────────────

    def _normalize(self, raw_items: list[dict], *, days: int) -> list[dict]:
        """
        Map source-specific dicts to the common Item schema.
        Applies recency gate: drops items older than `days`.
        """
        cutoff = int(time.time()) - days * 86_400
        normalized = []

        for raw in raw_items:
            created = int(raw.get("created_utc", raw.get("timestamp", 0)))
            if created and created < cutoff:
                continue

            url = raw.get("url", raw.get("link", ""))
            item_id = _stable_id(url or raw.get("id", ""))

            normalized.append(
                {
                    "id": item_id,
                    "source": self.source.value,
                    "title": (raw.get("title") or raw.get("name") or "")[:200],
                    "body": (
                        raw.get("selftext") or raw.get("text") or raw.get("description") or ""
                    )[:500],
                    "url": url,
                    "score": float(raw.get("score", raw.get("likes", raw.get("views", 0)))),
                    "created_utc": created,
                    "author": raw.get("author", raw.get("username", "")),
                    "tags": raw.get("tags", []),
                }
            )

        return normalized


# ── Source fetchers (stubs — replace with real API calls) ─────────────────────


async def _fetch_reddit(query: str, *, days: int) -> list[dict]:
    """
    Fetch from Reddit via ScrapeCreators API.
    Replace SCRAPECREATORS_API_KEY env var with real key.
    Falls back to Pushshift if primary fails (3-level degradation).
    """
    # Real implementation: call ScrapeCreators /reddit/search endpoint
    # See lib/sources/reddit.py for the full implementation
    await asyncio.sleep(0)  # yield to event loop
    return []


async def _fetch_twitter(query: str, *, days: int) -> list[dict]:
    """Fetch from X via xAI Grok API or Bird GraphQL client."""
    await asyncio.sleep(0)
    return []


async def _fetch_youtube(query: str, *, days: int) -> list[dict]:
    """Fetch YouTube search results + extract transcripts for top videos."""
    await asyncio.sleep(0)
    return []


async def _fetch_hn(query: str, *, days: int) -> list[dict]:
    """Fetch from Hacker News Algolia API (free, no key required)."""
    await asyncio.sleep(0)
    return []


async def _fetch_web(query: str, *, days: int) -> list[dict]:
    """Fetch from Brave Search API for general web results."""
    await asyncio.sleep(0)
    return []


async def _fetch_polymarket(query: str, *, days: int) -> list[dict]:
    """Fetch prediction market positions from Polymarket API."""
    await asyncio.sleep(0)
    return []


# ── Helpers ───────────────────────────────────────────────────────────────────


def _stable_id(value: str) -> str:
    """URL-stable 12-char hex id for deduplication."""
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()[:12]
