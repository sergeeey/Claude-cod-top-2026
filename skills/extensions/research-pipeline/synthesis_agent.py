"""
Synthesis Agent — creates the final research briefing from ranked items.
Verifier Agent — checks for hallucinations and low-confidence claims.

These two agents run in PARALLEL (Phase 3 of the pipeline) via asyncio.gather().
The synthesis agent writes the narrative; the verifier independently checks
the raw items for signals of misinformation or stale data.

Why parallel?
  Sequential: synthesis (45s) + verify (20s) = 65s
  Parallel:   max(45s, 20s) = 45s   →  30% faster
"""

import re
import time
from collections import Counter

# ══════════════════════════════════════════════════════════════════════════════
#  SYNTHESIS AGENT
# ══════════════════════════════════════════════════════════════════════════════

class SynthesisAgent:
    """
    Converts ranked items into a structured Markdown briefing.

    Structure:
      1. TL;DR (3–5 bullet points — highest signal)
      2. What people are saying (grouped by theme)
      3. Notable voices (top-mentioned authors/handles)
      4. Prompt pack (if items contain prompting content)
      5. Follow-up suggestions
    """

    async def run(
        self,
        items: list[dict],
        *,
        topic: str,
        context: dict | None = None,
    ) -> dict:
        """
        Build briefing Markdown from ranked items.

        CONTEXT LOADING: uses context to personalise the follow-up
        suggestions based on what was recently researched.
        """
        context = context or {}
        recent_topics: list[str] = context.get("recent_topics", [])

        if not items:
            return {"markdown": "_No items found._", "word_count": 0}

        sections: list[str] = []

        # ── TL;DR ─────────────────────────────────────────────────────────
        top5 = items[:5]
        tldr_lines = [f"- **{_clean(i['title'])}** ({i['source']})" for i in top5]
        sections.append("## TL;DR\n" + "\n".join(tldr_lines))

        # ── What people are saying (themed groups) ─────────────────────────
        themes = _cluster_by_theme(items, n_themes=4)
        theme_section = ["## What people are saying"]
        for theme_label, theme_items in themes.items():
            theme_section.append(f"\n### {theme_label}")
            for item in theme_items[:3]:
                snippet = _clean(item["body"])[:180]
                url = item.get("url", "")
                cite = f" ([{item['source']}]({url}))" if url else f" ({item['source']})"
                if snippet:
                    theme_section.append(f"> {snippet}…{cite}")
                else:
                    theme_section.append(f"- {_clean(item['title'])}{cite}")
        sections.append("\n".join(theme_section))

        # ── Notable voices ─────────────────────────────────────────────────
        authors = Counter(
            i["author"] for i in items if i.get("author")
        ).most_common(5)
        if authors:
            voices = ["## Notable voices"]
            for author, count in authors:
                voices.append(f"- **{author}** ({count} mention{'s' if count > 1 else ''})")
            sections.append("\n".join(voices))

        # ── Prompt pack ────────────────────────────────────────────────────
        prompt_items = [i for i in items if _is_prompt_content(i)]
        if prompt_items:
            pp = ["## Prompt pack"]
            pp.append(f"_{len(prompt_items)} items with actionable prompting techniques_\n")
            for item in prompt_items[:3]:
                pp.append(f"**{_clean(item['title'])}**")
                if item.get("body"):
                    pp.append(f"```\n{_clean(item['body'])[:300]}\n```")
            sections.append("\n".join(pp))

        # ── Follow-up suggestions ──────────────────────────────────────────
        suggestions = _generate_followups(topic, items, recent_topics=recent_topics)
        if suggestions:
            fu = ["## Dig deeper"]
            fu += [f"- `{s}`" for s in suggestions]
            sections.append("\n".join(fu))

        markdown = "\n\n".join(sections)
        word_count = len(markdown.split())

        return {"markdown": markdown, "word_count": word_count}


# ══════════════════════════════════════════════════════════════════════════════
#  VERIFIER AGENT
# ══════════════════════════════════════════════════════════════════════════════

class VerifierAgent:
    """
    Independently checks ranked items for quality signals.

    Runs in parallel with SynthesisAgent. Checks:
      - Recency: are items actually within the claimed window?
      - Engagement: are scores suspiciously high (bot-like)?
      - Source diversity: is this an echo chamber (single source)?
      - Stale cross-post: same content posted multiple times?

    Returns confidence level: HIGH / MEDIUM / LOW / SPECULATIVE
    """

    async def run(self, items: list[dict], *, topic: str) -> dict:
        if not items:
            return {"confidence": "SPECULATIVE", "flags": ["No items to verify"]}

        flags: list[str] = []
        now = int(time.time())

        # ── Recency check ──────────────────────────────────────────────────
        ages_days = [
            (now - i["created_utc"]) / 86_400
            for i in items
            if i.get("created_utc")
        ]
        if ages_days:
            median_age = sorted(ages_days)[len(ages_days) // 2]
            if median_age > 25:
                flags.append(
                    f"[WARN] Median item age is {median_age:.0f} days — "
                    "results may skew older than 30-day window"
                )

        # ── Source diversity ───────────────────────────────────────────────
        source_counts = Counter(i["source"] for i in items)
        dominant_source, dominant_n = source_counts.most_common(1)[0]
        if dominant_n / len(items) > 0.70:
            flags.append(
                f"[WARN] {dominant_n}/{len(items)} items from {dominant_source} — "
                "limited cross-platform validation"
            )

        # ── Engagement anomaly detection ───────────────────────────────────
        scores = [float(i.get("score", 0)) for i in items if i.get("score")]
        if scores:
            mean_s = sum(scores) / len(scores)
            outliers = [s for s in scores if s > mean_s * 20]
            if outliers:
                flags.append(
                    f"[INFO] {len(outliers)} item(s) have anomalously high engagement "
                    f"(>{mean_s * 20:.0f}) — may be viral rather than representative"
                )

        # ── Duplicate URL check ────────────────────────────────────────────
        urls = [i.get("url") for i in items if i.get("url")]
        dupe_urls = {u for u in urls if urls.count(u) > 1}
        if dupe_urls:
            flags.append(
                f"[WARN] {len(dupe_urls)} duplicate URL(s) passed dedup — "
                "funnel threshold may need tuning"
            )

        # ── Confidence verdict ─────────────────────────────────────────────
        n_sources = len(source_counts)
        n_warn_flags = sum(1 for f in flags if "[WARN]" in f)

        if n_sources >= 3 and n_warn_flags == 0:
            confidence = "HIGH"
        elif n_sources >= 2 and n_warn_flags <= 1:
            confidence = "MEDIUM"
        elif n_warn_flags >= 2:
            confidence = "LOW"
        else:
            confidence = "MEDIUM"

        return {"confidence": confidence, "flags": flags}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Strip markdown artifacts and normalise whitespace."""
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:500]


def _is_prompt_content(item: dict) -> bool:
    """Heuristic: item likely contains prompting techniques."""
    keywords = {"prompt", "prompting", "technique", "template", "format", "token"}
    text = (item.get("title", "") + " " + item.get("body", "")).lower()
    return sum(1 for kw in keywords if kw in text) >= 2


def _cluster_by_theme(
    items: list[dict], n_themes: int = 4
) -> dict[str, list[dict]]:
    """
    Simple keyword-based theme clustering.
    For production: replace with embedding-based clustering.
    """
    # Collect all significant words
    word_counts: Counter = Counter()
    for item in items:
        words = re.findall(r"[a-z]{4,}", (item.get("title", "")).lower())
        word_counts.update(words)

    STOP = frozenset("that this with from have been they there their then".split())
    top_words = [w for w, _ in word_counts.most_common(20) if w not in STOP]
    theme_words = top_words[:n_themes]

    themes: dict[str, list[dict]] = {w.title(): [] for w in theme_words}
    themes["Other"] = []

    assigned: set[str] = set()
    for item in items:
        title_lower = item.get("title", "").lower()
        placed = False
        for word in theme_words:
            if word in title_lower and item["id"] not in assigned:
                themes[word.title()].append(item)
                assigned.add(item["id"])
                placed = True
                break
        if not placed and item["id"] not in assigned:
            themes["Other"].append(item)
            assigned.add(item["id"])

    return {k: v for k, v in themes.items() if v}


def _generate_followups(
    topic: str, items: list[dict], *, recent_topics: list[str]
) -> list[str]:
    """
    Suggest follow-up research queries based on:
      - Top co-occurring terms not in the original topic
      - Topics NOT recently researched (from CONTEXT LOADING)
    """
    topic_tokens = set(re.findall(r"[a-z]{4,}", topic.lower()))
    co_terms: Counter = Counter()
    for item in items[:15]:
        words = re.findall(r"[a-z]{5,}", (item.get("title", "")).lower())
        for w in words:
            if w not in topic_tokens:
                co_terms[w] += 1

    suggestions: list[str] = []
    for term, _ in co_terms.most_common(5):
        candidate = f"{topic} {term}"
        if not any(candidate in rt for rt in recent_topics):
            suggestions.append(candidate)

    return suggestions[:3]
