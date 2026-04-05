"""Shared Claude Code tips catalog for learning_tracker.py and session_start.py.

Organised by level 1 (beginner) → 5 (expert).
Each tip: id, level, tag, text, next_try action.
"""

from pathlib import Path

LEARNING_LOG_PATH = Path.home() / ".claude" / "memory" / "learning_log.md"

# ── Tip catalog ───────────────────────────────────────────────────────────────

TIPS: list[dict] = [
    # Level 1 — Foundations
    {
        "id": "L1-T01",
        "level": 1,
        "tag": "memory",
        "text": "CLAUDE.md загружается в каждой сессии автоматически.\n"
        "Добавь в него ключевые факты проекта — Claude не забудет.",
        "next_try": "Открой ~/.claude/CLAUDE.md и добавь одно предложение о текущем проекте.",
    },
    {
        "id": "L1-T02",
        "level": 1,
        "tag": "slash",
        "text": "/compact сжимает контекст когда он заполнен на 50%+.\n"
        "Запускай проактивно — не жди красного статуса.",
        "next_try": "Напечатай /compact прямо сейчас и посмотри как счётчик токенов сбросится.",
    },
    {
        "id": "L1-T03",
        "level": 1,
        "tag": "slash",
        "text": "/clear — чистый контекст без закрытия сессии.\n"
        "Идеально при смене задачи внутри сессии.",
        "next_try": "При следующей смене задачи используй /clear вместо нового терминала.",
    },
    {
        "id": "L1-T04",
        "level": 1,
        "tag": "permissions",
        "text": "Claude Code спрашивает разрешение на каждую операцию.\n"
        "settings.json allow/deny списки позволяют пре-одобрить безопасные паттерны.",
        "next_try": "Запусти 'claude mcp list' чтобы увидеть активные инструменты.",
    },
    {
        "id": "L1-T05",
        "level": 1,
        "tag": "slash",
        "text": "/think и /think harder дают Claude время на глубокое размышление.\n"
        "Используй для архитектурных решений и сложных багов.",
        "next_try": "Начни следующий сложный запрос с /think harder и сравни качество ответа.",
    },
    # Level 2 — Productivity
    {
        "id": "L2-T01",
        "level": 2,
        "tag": "tdd",
        "text": "TDD с Claude: сначала дай упавший тест, потом попроси его пофиксить.\n"
        "Результат тестируемее и точнее требований.",
        "next_try": "Напиши 'test_' функцию первой, получи RED, потом попроси Claude сделать GREEN.",
    },
    {
        "id": "L2-T02",
        "level": 2,
        "tag": "hooks",
        "text": "PostToolUse хуки срабатывают после каждого вызова инструмента.\n"
        "Ноль токенов, 100% детерминировано — нельзя обойти через промпт.",
        "next_try": "Прочти hooks/memory_guard.py — 66 строк, показывает полный паттерн хука.",
    },
    {
        "id": "L2-T03",
        "level": 2,
        "tag": "skills",
        "text": "Скиллы активируются по ключевым словам в промпте.\n"
        "'tests' → TDD workflow, 'security' → аудит, 'worktree' → git-worktrees.",
        "next_try": "Начни следующий запрос с 'tests:' и посмотри как routing изменится.",
    },
    {
        "id": "L2-T04",
        "level": 2,
        "tag": "memory",
        "text": "~/.claude/memory/ — долгосрочная память Claude.\n"
        "activeContext.md, decisions.md, patterns.md живут между сессиями.",
        "next_try": "Открой patterns.md и прочти последние 3 записи — это баги из твоих сессий.",
    },
    {
        "id": "L2-T05",
        "level": 2,
        "tag": "mcp",
        "text": "MCP серверы расширяют Claude инструментами: БД, браузер, API.\n"
        "'claude mcp list' показывает всё подключённое прямо сейчас.",
        "next_try": "Запусти 'claude mcp list' для инвентаризации.",
    },
    # Level 3 — Advanced Workflows
    {
        "id": "L3-T01",
        "level": 3,
        "tag": "worktree",
        "text": "git worktree add ../experiment — запускает Claude на ветке\n"
        "без stash. Полная изоляция, чистое рабочее дерево.",
        "next_try": "Создай worktree для следующего экспериментального изменения.",
    },
    {
        "id": "L3-T02",
        "level": 3,
        "tag": "agents",
        "text": "Sub-агенты (Task tool) работают в изолированном контексте.\n"
        "Возвращают только результат — их контекст не засоряет твой.",
        "next_try": "Попроси Claude использовать 'review-squad' на diff последнего PR.",
    },
    {
        "id": "L3-T03",
        "level": 3,
        "tag": "hooks",
        "text": "PreToolUse хуки с exit code 2 БЛОКИРУЮТ вызов инструмента.\n"
        "Используй для политик: 'нет прямых пушей в main'.",
        "next_try": "Прочти hooks/pre_commit_guard.py — видно какие операции сейчас заблокированы.",
    },
    {
        "id": "L3-T04",
        "level": 3,
        "tag": "plan",
        "text": "Plan Mode заставляет Claude описать все изменения файлов\n"
        "до того как сделать хоть одно. Обязателен при 3+ файлах.",
        "next_try": "Начни следующий рефакторинг с 'Plan: переименовать X в Y во всех файлах'.",
    },
    {
        "id": "L3-T05",
        "level": 3,
        "tag": "evidence",
        "text": "Evidence Policy: [VERIFIED] = проверено инструментом,\n"
        "[INFERRED] = логический вывод, [UNKNOWN] = нужна проверка.",
        "next_try": "Спроси: 'Что [VERIFIED] vs [INFERRED] в текущей реализации?'",
    },
    {
        "id": "L3-T06",
        "level": 3,
        "tag": "tokens",
        "text": "spinnerTipsOverride в settings.json — бесплатный канал подсказок\n"
        "пока Claude думает. Ноль токенов контекста.",
        "next_try": "Добавь специфичную подсказку проекта в spinnerTipsOverride.",
    },
    # Level 4 — System Architecture
    {
        "id": "L4-T01",
        "level": 4,
        "tag": "hooks",
        "text": "async_wrapper.py отсоединяет медленные хуки как фоновые процессы.\n"
        "Claude Code никогда не ждёт их завершения.",
        "next_try": "Добавь async_wrapper.py префикс к любому хуку который пишет на диск.",
    },
    {
        "id": "L4-T02",
        "level": 4,
        "tag": "mcp",
        "text": "Circuit Breaker: mcp_circuit_breaker.py считает отказы MCP.\n"
        "После 3 отказов авто-отключает сервер на 60 секунд.",
        "next_try": "Прочти hooks/mcp_circuit_breaker.py чтобы увидеть машину состояний.",
    },
    {
        "id": "L4-T03",
        "level": 4,
        "tag": "agents",
        "text": "Agent Teams: несколько sub-агентов параллельно через Task tool.\n"
        "review-squad запускает reviewer + sec-auditor одновременно.",
        "next_try": "Скажи Claude: 'Используй review-squad для проверки diff последнего коммита'.",
    },
    {
        "id": "L4-T04",
        "level": 4,
        "tag": "statusline",
        "text": "statusline.py формирует статусбар внизу терминала.\n"
        "Ветка, coverage, счётчик хуков — всё за ноль токенов.",
        "next_try": "Открой hooks/statusline.py и добавь метрику важную для твоего проекта.",
    },
    # Level 5 — Expert
    {
        "id": "L5-T01",
        "level": 5,
        "tag": "hooks",
        "text": "emit_hook_result() инжектирует текст в контекст Claude как\n"
        "additionalContext — детерминированный prompt injection под твоим контролем.",
        "next_try": "Напиши хук который читает файл и инжектирует ключевые строки как контекст.",
    },
    {
        "id": "L5-T02",
        "level": 5,
        "tag": "routing",
        "text": "UserPromptSubmit хуки запускаются ДО того как Claude читает сообщение.\n"
        "Классифицируют намерение и вставляют routing hints до любого LLM вызова.",
        "next_try": "Прочти hooks/keyword_router.py — он маршрутизирует задачи за <5ms.",
    },
    {
        "id": "L5-T03",
        "level": 5,
        "tag": "memory",
        "text": "Многоуровневая память: CLAUDE.md = горячая (каждая сессия),\n"
        "memory/*.md = тёплая (по требованию), logs/ = холодная (архив).",
        "next_try": "Перенеси редко нужный факт из CLAUDE.md в memory/techContext.md.",
    },
    {
        "id": "L5-T04",
        "level": 5,
        "tag": "hooks",
        "text": "PermissionRequest хуки авто-одобряют паттерны.\n"
        "Текущий конфиг авто-одобряет Read/Glob/Grep — -75% попапов разрешений.",
        "next_try": "Прочти hooks/permission_policy.py и добавь паттерн который ты одобряешь каждый день.",
    },
]

# ── Tip selection ─────────────────────────────────────────────────────────────

_COMMIT_TYPE_TAG_MAP: dict[str, list[str]] = {
    "feat": ["skills", "agents", "plan", "worktree"],
    "fix": ["tdd", "hooks", "evidence"],
    "refactor": ["plan", "worktree", "agents", "hooks"],
    "test": ["tdd", "hooks", "evidence"],
    "chore": ["memory", "slash", "tokens", "statusline"],
    "docs": ["memory", "evidence", "slash"],
    "other": ["hooks", "memory", "slash"],
}


def _shown_tip_ids(log_content: str) -> list[str]:
    """Extract tip IDs already shown from the ## Machine Log section."""
    ids: list[str] = []
    in_table = False
    for line in log_content.splitlines():
        if line.strip().startswith("## Machine Log"):
            in_table = True
            continue
        if in_table and line.startswith("|") and not line.startswith("| Date"):
            parts = [p.strip() for p in line.split("|")]
            # cols: Date | Commit | Type | Tip ID | Files
            if len(parts) >= 5:
                tip_id = parts[4]  # index 4 due to leading |
                if tip_id and tip_id != "Tip ID" and not tip_id.startswith("-"):
                    ids.append(tip_id)
    return ids


def select_tip(log_content: str = "", commit_type: str = "other") -> dict:
    """Select the next unseen tip, preferring tags relevant to commit_type.

    Cycles back to beginning if all tips have been shown.
    Always returns a valid tip dict.
    """
    shown = set(_shown_tip_ids(log_content))
    preferred_tags = set(_COMMIT_TYPE_TAG_MAP.get(commit_type, ["hooks", "memory"]))

    # 1st pass: preferred tag, not yet shown
    for tip in TIPS:
        if tip["id"] not in shown and tip["tag"] in preferred_tags:
            return tip

    # 2nd pass: any tag, not yet shown
    for tip in TIPS:
        if tip["id"] not in shown:
            return tip

    # 3rd pass: all shown — restart cycle (learning spiral)
    for tip in TIPS:
        if tip["tag"] in preferred_tags:
            return tip

    return TIPS[0]
