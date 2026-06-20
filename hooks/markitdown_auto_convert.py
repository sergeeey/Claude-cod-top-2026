#!/usr/bin/env python3
"""SessionStart hook — auto-converts new documents in raw/ to Markdown.

Сканирует ~/.claude/memory/raw/ при старте сессии. Если найдены файлы
поддерживаемых форматов (PDF, DOCX, PPTX, XLSX, HTML, etc.) без соседнего
.md эквивалента — конвертирует через markitdown.

Цель: экономия токенов и удобная работа с документами в LLM-context.

Идемпотентность:
- Конвертирует ТОЛЬКО если <stem>.md ещё не существует
- Логирует результаты в ~/.claude/logs/markitdown_convert.log
- Не падает если markitdown не установлен (silent skip)

Recursion guard: уважает CLAUDE_INVOKED_BY env var.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Recursion guard
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

RAW_DIR = Path.home() / ".claude" / "memory" / "raw"
LOG_FILE = Path.home() / ".claude" / "logs" / "markitdown_convert.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Форматы которые markitdown понимает
SUPPORTED_EXTS = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".epub",
    ".msg",
    ".rtf",
    ".odt",
    ".odp",
    ".ods",
}

# Skip если markitdown не установлен — это hook должен быть soft
try:
    from markitdown import MarkItDown
except ImportError:
    sys.exit(0)

# Skip если raw/ ещё не создан
if not RAW_DIR.exists():
    sys.exit(0)


def _log(entry: dict) -> None:
    """Записать запись в лог."""
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _find_unconverted() -> list[Path]:
    """Найти файлы которые ещё не были сконвертированы."""
    candidates = []
    for f in RAW_DIR.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in SUPPORTED_EXTS:
            continue
        # Если соседний .md уже существует — пропускаем
        md_sibling = f.with_suffix(".md")
        if md_sibling.exists():
            continue
        candidates.append(f)
    return candidates


def _convert(file_path: Path, md: MarkItDown) -> tuple[bool, str]:
    """Конвертировать один файл. Возвращает (success, message)."""
    try:
        result = md.convert(str(file_path))
        out_path = file_path.with_suffix(".md")

        # Заголовок-метка чтобы было видно что это автоконверт
        header = (
            f"<!-- Auto-converted from {file_path.name} by markitdown_auto_convert.py "
            f"on {datetime.now(UTC).isoformat()} -->\n\n"
        )
        out_path.write_text(header + result.text_content, encoding="utf-8")
        return True, f"OK: {file_path.name} -> {out_path.name}"
    except Exception as e:
        return False, f"FAIL: {file_path.name} -> {type(e).__name__}: {e}"


def main() -> int:
    unconverted = _find_unconverted()
    if not unconverted:
        sys.exit(0)

    md = MarkItDown()
    converted = []
    failed = []

    for f in unconverted:
        success, msg = _convert(f, md)
        if success:
            converted.append(f.name)
        else:
            failed.append(f.name)

        _log(
            {
                "ts": datetime.now(UTC).isoformat(),
                "source": str(f),
                "success": success,
                "message": msg,
            }
        )

    # Эмитим additionalContext чтобы Claude видел что произошло
    if converted or failed:
        msg_parts = []
        if converted:
            msg_parts.append(f"converted: {', '.join(converted)}")
        if failed:
            msg_parts.append(f"failed: {', '.join(failed)}")
        notice = f"[markitdown-auto] {' | '.join(msg_parts)}"

        # JSON output для SessionStart hook
        output = {
            "continue": True,
            "additionalContext": notice,
        }
        sys.stdout.write(json.dumps(output))

    return 0


if __name__ == "__main__":
    sys.exit(main())
