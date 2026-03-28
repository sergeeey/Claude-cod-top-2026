"""
Shared state management for the last30days multi-agent pipeline.

This module is the CONTEXT LOADING backbone: agents read project state
before acting and write results back so the next run is context-aware.

Files managed:
  ~/.claude/memory/activeContext.md   — human-readable session state
  ~/.claude/memory/last30days_state.json — machine-readable pipeline state
"""

import json
import re
from datetime import datetime
from pathlib import Path

_CONTEXT_FILE = "activeContext.md"
_STATE_FILE = "last30days_state.json"
_MAX_HISTORY = 20


class SharedState:
    """
    Lightweight key-value store backed by Markdown + JSON files.
    Designed to be readable by humans and Claude Code agents alike.
    """

    def __init__(self, context_dir: Path | None = None) -> None:
        self.dir = context_dir or Path.home() / ".claude" / "memory"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._context_path = self.dir / _CONTEXT_FILE
        self._state_path = self.dir / _STATE_FILE

    # ── Read ──────────────────────────────────────────────────────────────

    def load_context(self) -> dict:
        """
        CONTEXT LOADING: parse activeContext.md into structured dict.
        Returns empty dict if the file doesn't exist (graceful degradation).

        Agents call this before any work to know:
          - current_focus: what is the main ongoing task
          - recent_topics: last researched topics (avoid duplicates)
          - decisions: architectural choices affecting output format
        """
        result: dict = {}

        if not self._context_path.exists():
            return result

        text = self._context_path.read_text(encoding="utf-8")

        # Extract key sections using heading markers
        for match in re.finditer(
            r"##\s+(.+?)\n(.*?)(?=\n##|\Z)", text, re.DOTALL
        ):
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            result[key] = value

        # Extract structured state if embedded
        if self._state_path.exists():
            try:
                machine = json.loads(self._state_path.read_text(encoding="utf-8"))
                result.update(machine)
            except json.JSONDecodeError:
                pass

        return result

    def load_recent_topics(self) -> list[str]:
        """Return list of recently researched topics (for dedup hints)."""
        state = self._load_machine_state()
        return state.get("recent_topics", [])

    # ── Write ─────────────────────────────────────────────────────────────

    def update_last_run(self, topic: str, stats: dict) -> None:
        """
        Called by the orchestrator after a successful run.
        Updates both human-readable activeContext.md and machine state.
        """
        state = self._load_machine_state()

        # Rolling history
        history: list[dict] = state.get("run_history", [])
        history.insert(0, {
            "topic": topic,
            "timestamp": stats["timestamp"],
            "elapsed_s": stats["elapsed_s"],
            "confidence": stats["confidence"],
            "items": stats["ranked_items"],
        })
        state["run_history"] = history[:_MAX_HISTORY]

        # Recent topics (for context-aware dedup)
        recent: list[str] = state.get("recent_topics", [])
        if topic not in recent:
            recent.insert(0, topic)
        state["recent_topics"] = recent[:10]

        self._save_machine_state(state)
        self._update_context_md(topic, stats)

    def set_focus(self, focus: str) -> None:
        """Allow Claude Code to set the current project focus."""
        self._patch_context_section("current_focus", focus)

    # ── Internal ──────────────────────────────────────────────────────────

    def _load_machine_state(self) -> dict:
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_machine_state(self, state: dict) -> None:
        self._state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _update_context_md(self, topic: str, stats: dict) -> None:
        """Append a summary entry to activeContext.md."""
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        entry = (
            f"\n## Last run\n"
            f"- **Topic**: {topic}\n"
            f"- **Time**: {ts}\n"
            f"- **Elapsed**: {stats['elapsed_s']}s\n"
            f"- **Confidence**: {stats['confidence']}\n"
            f"- **Items**: {stats['ranked_items']} ranked\n"
        )
        existing = ""
        if self._context_path.exists():
            existing = self._context_path.read_text(encoding="utf-8")
            # Remove stale "Last run" section
            existing = re.sub(r"\n## Last run\n.*?(?=\n##|\Z)", "", existing, flags=re.DOTALL)

        self._context_path.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")

    def _patch_context_section(self, section: str, value: str) -> None:
        """Upsert a named section in activeContext.md."""
        header = f"## {section.replace('_', ' ').title()}"
        block = f"{header}\n{value}\n"
        existing = ""
        if self._context_path.exists():
            existing = self._context_path.read_text(encoding="utf-8")
        pattern = rf"{re.escape(header)}\n.*?(?=\n##|\Z)"
        if re.search(pattern, existing, re.DOTALL):
            existing = re.sub(pattern, block.rstrip(), existing, flags=re.DOTALL)
        else:
            existing = existing.rstrip() + "\n\n" + block
        self._context_path.write_text(existing, encoding="utf-8")
