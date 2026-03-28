"""
Funnel Agent — scoring, deduplication, and ranking across all sources.

This is Phase 2 of the pipeline: takes raw items from all discovery agents
and produces a ranked, deduplicated list ready for synthesis.

Scoring formula (weighted sum, all values normalized to [0, 1]):
  engagement_velocity  × 0.40   — engagement / age (newer = higher)
  cross_source_boost   × 0.25   — same topic mentioned on multiple platforms
  recency_score        × 0.20   — freshness within the recency window
  content_quality      × 0.15   — body length, has url, has author

The cross_source_boost is the key multi-agent feature: an item that
appears (or its topic appears) on both Reddit AND Twitter gets a bonus,
indicating genuine signal rather than single-platform echo.
"""

import re
import time
from collections import defaultdict
from difflib import SequenceMatcher

_STOP_WORDS = frozenset(
    "the a an is are was were be been being have has had do does did "
    "will would could should may might shall can for of to in on at "
    "by with from about into through during after before".split()
)


class FunnelAgent:
    """
    Score, deduplicate, and rank all discovery results.

    Args:
        top_k_per_source: Hard limit per source before global ranking.
        top_k_final:      Final number of items passed to synthesis.
        dedup_threshold:  Title similarity above this → treat as duplicate.
    """

    def __init__(
        self,
        top_k_per_source: int = 10,
        top_k_final: int = 30,
        dedup_threshold: float = 0.82,
    ) -> None:
        self.top_k_per_source = top_k_per_source
        self.top_k_final = top_k_final
        self.dedup_threshold = dedup_threshold

    async def run(self, items: list[dict], *, topic: str) -> dict:
        """
        Process raw items → ranked, deduplicated list.

        Returns:
            {
                "ranked": list[dict],    # top items with score field added
                "dedup_removed": int,
                "source_breakdown": dict,
            }
        """
        if not items:
            return {"ranked": [], "dedup_removed": 0, "source_breakdown": {}}

        now = int(time.time())
        topic_tokens = _tokenize(topic)

        # ── Step 1: Score each item ───────────────────────────────────────
        for item in items:
            item["_score"] = self._score(item, now=now, topic_tokens=topic_tokens)

        # ── Step 2: Per-source top-k (prevents one source dominating) ─────
        by_source: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            by_source[item["source"]].append(item)

        source_breakdown: dict[str, int] = {}
        capped: list[dict] = []
        for source, src_items in by_source.items():
            src_items.sort(key=lambda x: x["_score"], reverse=True)
            kept = src_items[: self.top_k_per_source]
            capped.extend(kept)
            source_breakdown[source] = len(kept)

        # ── Step 3: Cross-source boost ────────────────────────────────────
        title_index: dict[str, list[dict]] = defaultdict(list)
        for item in capped:
            key = _title_fingerprint(item["title"])
            title_index[key].append(item)

        for item in capped:
            key = _title_fingerprint(item["title"])
            n_sources = len({x["source"] for x in title_index[key]})
            if n_sources > 1:
                item["_score"] *= 1.0 + 0.12 * (n_sources - 1)

        # ── Step 4: Semantic deduplication ────────────────────────────────
        ranked, removed = self._dedup(capped)

        # ── Step 5: Global sort + top-k ───────────────────────────────────
        ranked.sort(key=lambda x: x["_score"], reverse=True)
        ranked = ranked[: self.top_k_final]

        # Rename internal score to public field
        for item in ranked:
            item["relevance_score"] = round(item.pop("_score"), 4)

        return {
            "ranked": ranked,
            "dedup_removed": removed,
            "source_breakdown": source_breakdown,
        }

    # ── Scoring ───────────────────────────────────────────────────────────

    def _score(self, item: dict, *, now: int, topic_tokens: set[str]) -> float:
        age_s = max(1, now - item.get("created_utc", now))
        age_days = age_s / 86_400

        # Engagement velocity: normalize score by age in days
        raw_engagement = max(0.0, float(item.get("score", 0)))
        velocity = raw_engagement / age_days if age_days > 0 else 0.0
        # Soft-cap: log scale to prevent viral posts from dominating
        import math
        velocity_norm = math.log1p(velocity) / 10.0  # 0..~1

        # Recency: 1.0 = today, 0.0 = window edge
        recency = max(0.0, 1.0 - age_days / 30.0)

        # Content quality signals
        has_body = 1.0 if len(item.get("body", "")) > 50 else 0.0
        has_url = 1.0 if item.get("url") else 0.0
        has_author = 0.5 if item.get("author") else 0.0
        quality = (has_body + has_url + has_author) / 2.5

        # Topic relevance: fraction of topic tokens in title+body
        text_tokens = _tokenize(item.get("title", "") + " " + item.get("body", ""))
        if topic_tokens:
            relevance = len(topic_tokens & text_tokens) / len(topic_tokens)
        else:
            relevance = 0.5

        return (
            velocity_norm * 0.35
            + relevance   * 0.25
            + recency     * 0.25
            + quality     * 0.15
        )

    # ── Deduplication ─────────────────────────────────────────────────────

    def _dedup(self, items: list[dict]) -> tuple[list[dict], int]:
        """
        Remove near-duplicate items using title similarity.
        Keeps the higher-scored item when a duplicate pair is found.
        O(n²) — acceptable for n≤200.
        """
        items = sorted(items, key=lambda x: x["_score"], reverse=True)
        kept: list[dict] = []
        removed = 0

        for candidate in items:
            c_title = candidate.get("title", "").lower()
            is_dup = False
            for existing in kept:
                e_title = existing.get("title", "").lower()
                ratio = SequenceMatcher(None, c_title, e_title).ratio()
                if ratio >= self.dedup_threshold:
                    is_dup = True
                    break
            if is_dup:
                removed += 1
            else:
                kept.append(candidate)

        return kept, removed


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z]{3,}", text.lower())
    return {w for w in words if w not in _STOP_WORDS}


def _title_fingerprint(title: str) -> str:
    """Reduce title to a short fingerprint for grouping similar titles."""
    tokens = sorted(_tokenize(title))[:6]
    return " ".join(tokens)
