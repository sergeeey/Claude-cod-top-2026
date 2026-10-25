---
name: convert
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-06-01]
  Конвертирует PDF/DOCX/PPTX/XLSX/HTML/audio/YouTube/изображения в Markdown через Microsoft markitdown.
  Экономит 5-10x токенов на больших документах перед чтением Claude.
  Сохраняет результат рядом с исходником (file.pdf → file.md). Идемпотентен.
  Triggers: /convert, конвертируй документ, преврати в markdown, "pdf в markdown",
  "docx в markdown", convert to markdown, "сделай markdown из", markitdown,
  "переведи документ", "обработай PDF". Используй когда у тебя есть документ
  любого формата и хочешь работать с ним в Claude без лишних токенов.
  НЕ для: уже markdown-файлов, очень больших PDF (>100MB — split first).
effort: minimal
tokens: ~300
triggers: [/convert, "конвертируй документ", "преврати в markdown", "pdf в markdown", "docx в markdown", "convert to markdown", "сделай markdown из", markitdown, "переведи документ", "обработай PDF"]
---

<!-- BSV — Brief Skill View | поиск: BSV
Скил   : convert
TL;DR  : PDF/DOCX/PPTX/audio/YouTube → Markdown через MS markitdown. Экономия 5-10x токенов
Вызов  : /convert <file_or_url>, конвертируй документ
НЕ для : Уже markdown файлов, очень больших PDF (split first)
-->

# /convert — Document → Markdown

Конвертирует документ в Markdown через [Microsoft markitdown](https://github.com/microsoft/markitdown). Локально, бесплатно, ~18 converters.

## Поддерживаемые форматы

| Категория | Расширения |
|---|---|
| Документы | `.pdf`, `.docx`, `.doc`, `.rtf`, `.odt` |
| Презентации | `.pptx`, `.ppt`, `.odp` |
| Таблицы | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.ods` |
| Веб | `.html`, `.htm`, YouTube URL |
| Email | `.msg` (Outlook) |
| Книги | `.epub` |
| Данные | `.json`, `.xml` |
| Архивы | `.zip` (рекурсивно) |
| Аудио (если установлен `markitdown[audio]`) | `.mp3`, `.wav` |
| Изображения (если установлен `markitdown[ocr]`) | `.png`, `.jpg` |

## Установка

```bash
# Минимум:
pip install markitdown

# С audio + OCR + всеми converters:
pip install markitdown[all]
```

## Использование

### Вариант 1: CLI напрямую
```bash
markitdown paper.pdf > paper.md
markitdown report.docx > report.md
markitdown https://www.youtube.com/watch?v=XXX > transcript.md
```

### Вариант 2: Через этот skill
Скажи в чате одно из:
- `/convert paper.pdf`
- `конвертируй report.docx`
- `преврати https://youtube.com/watch?v=... в markdown`

Я:
1. Найду исходный файл
2. Запущу markitdown
3. Сохраню `paper.md` рядом с `paper.pdf`
4. Покажу превью результата

## Когда применять

| Ситуация | Действие |
|---|---|
| Скачал PDF научной статьи | `/convert paper.pdf` → дальше Claude работает с .md |
| Получил DOCX с отчётом | `/convert report.docx` |
| Хочешь обработать YouTube лекцию | `/convert https://youtu.be/...` |
| Excel с данными | `/convert data.xlsx` → table в md format |

## Экономия токенов (примерные оценки)

| Формат | Прямой | После markitdown | Saving |
|---|---|---|---|
| 20-стр PDF научной статьи | ~50K tokens | ~5-8K tokens | **6-10x** |
| 50-стр DOCX доклад | ~100K tokens | ~15K tokens | **6-7x** |
| Excel 10 sheets | ~30K tokens | ~5K tokens | **6x** |
| YouTube 30 min | (нет vision) | ~3-5K tokens | enable read |

## Companion skills

- `/defuddle` — web страницы (HTML с шумом), если установлен

## Ограничения

| Lim | Что | Mitigation |
|---|---|---|
| Сложные таблицы PDF | Структура может теряться | Использовать Docling для critical tables |
| Математические формулы | LaTeX рендеринг хромает | Manual review для math-heavy |
| Scanned PDF (image-only) | Нужен OCR | `pip install markitdown[ocr]` |
| Audio transcription | Медленно (~1x realtime) | Запускать в фоне |
| >100MB файлы | Slow / OOM | Split tool first |

## Output format

Markdown файл сохраняется **рядом** с исходником:
- `paper.pdf` → `paper.md`
- `report.docx` → `report.md`

Файл начинается с auto-generated header:
```markdown
<!-- Auto-converted from <name> by markitdown -->
```

## Reference

- GitHub: github.com/microsoft/markitdown
- License: MIT
- Maintainer: Microsoft AutoGen team
- Sister tools: defuddle (web), Docling (IBM, complex layout)
