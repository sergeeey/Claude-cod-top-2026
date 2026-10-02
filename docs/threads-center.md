# Threads center

`scripts/threads_center.py` answers one question in the first ten seconds: **what is overdue, what is
open, and what is waiting for an event** — across the places where reminders used to get lost.

It is a derived view, not a new tracker. Nothing has to be entered by hand for the page to be full.

## Why it exists (history)

Measured on 2026-10-02, before the script existed:

* four weekly Claude tasks failed every run (Task Scheduler result 1, `claude -p` → `401 API key is
  invalid`) and nobody saw it, because a failing scheduled task is silent;
* 14 automated PRs sat open for up to 63 days, each adding a file to `.claude/memory/raw`;
* pearl-registry `next_check` dates had passed with no watcher, some marked "lapsed, not re-checked"
  since 2026-08-04;
* most "active" Obsidian notes were untouched for months while their mtime looked fresh, and five
  different notes claimed to be the "current state".

The same defect class as the Research/Evidence Loop's Cycle 1 (a mechanism that is silent is
indistinguishable from one that approves), so the design follows its measured lesson: **derive from
artifacts that already exist; a new manual field would have had zero coverage.**

## What it reads

| Collector | Source | What becomes a row |
|---|---|---|
| `automations` | Windows Task Scheduler (PowerShell `Get-ScheduledTask`) + task logs | task whose last result is not success/running, or with missed runs → overdue; never-run or **disabled** tasks → open |
| `pearls` | pearl registries (`~/.claude/rules/pearl_registry/INDEX.md`, the repo's `pearl_registry/INDEX.md`) | open rows with a `next_check` date in the past → overdue; undated trigger → waiting; a row whose cell count is wrong → open, "parsed unreliably" |
| `prs` | `gh pr list -R <owner/name>` | human PR with red CI or older than 14 days → overdue; automated PRs collapse into one line |
| `git` | `git worktree list` (incl. detached HEAD) + `git status` + one `gh pr list --head <branch>` per worktree branch | dirty worktrees (junk paths ignored), branches whose PRs were all closed without merge (a repo-wide `--limit 200` query would lose old branches in a long-lived repo) |
| `experiments` | `experiments/*` | folders with no verdict and no change for a long time ("zombies") |
| `waiting` | `experiments/*/ledger.md`, `parked/INDEX.md` | "check after …" conditions and parked rows (never overdue: they wait for an event) |
| `threads` | the thread store (below) | manually captured threads |
| `vault` | Obsidian hubs (`Dashboard`, `MEMORY`, status registries, `mocs/*`) | hubs untouched for 30+ days, hubs whose own "updated" date is older than their mtime says, claims that no longer match reality (file counts, open-PR counts), broken wikilinks, hubs with no links at all |

## How to read it

* **ПРОСРОЧЕНО** — something has a date or a failure that already passed. Look here first.
* **ОТКРЫТЫЕ НИТИ** — alive, no deadline hit yet.
* **ЖДУТ СОБЫТИЯ** — deliberately waiting for a condition, not a date. Not a problem; listed so they are not forgotten.
* **в списке** — how many days the row has been in the report since the first `render` on this machine. "новое" means *first noticed*, not *started today*: there is no history before the first render.
* **НЕ ПРОВЕРЕНО** — a source could not be read at all (no `gh`, no scheduler, missing registry). This is **not** "zero items".
* **ЧАСТИЧНО** — a source was read but part of it was not (e.g. `git status` failed in one worktree, one registry had no recognisable header). Listed in the coverage section with the reason.
* **Не охвачено** — what the script cannot see at all (Claude Desktop scheduled tasks, claude.ai cloud routines).
* Every kind of row is explained at the bottom of the note ("ЧТО ЭТО ЗА СТРОКИ").

If every source fails the status is `INSUFFICIENT_DATA`, nothing is written and the exit code is 2.

## Commands

```bash
python scripts/threads_center.py render --dry-run   # collect, print the summary, write nothing
python scripts/threads_center.py render             # write the note, the HTML page, this week's archive and the history
python scripts/threads_center.py summary --alert    # 3-line digest; exit 1 overdue, 2 something unchecked, 0 clean
python scripts/threads_center.py collect --json     # raw snapshot
python scripts/threads_center.py add "check X" --trigger "date:2026-11-01" --next "open file Y"
python scripts/threads_center.py close T-20261002-01 --status done
python scripts/threads_center.py list
python scripts/threads_center.py stats              # the kill criterion, computed (see below)
python scripts/threads_center.py install-hint       # prints the weekly schedule command, runs nothing
```

## What `render` writes (and only this)

| File | Content | Overwritten? |
|---|---|---|
| `<vault>/09 System/Центр нитей.md` | the live note | every render |
| `<vault>/09 System/Центр нитей (архив)/YYYY-Www.md` | the weekly snapshot, links to the live note and to earlier weeks | the same week's file is replaced, a new week adds a new file |
| `~/.claude/state/threads-center.html` | self-contained page (dark-mode aware, no scripts, no external resources) | every render |
| `~/.claude/state/threads-center-last.json` | a small summary for the SessionStart hook (below) | every render |
| `~/.claude/state/threads-center-seen-<scope>.json` | when each row was first/last listed and since when it was overdue | updated in place; a damaged file is set aside as `*.corrupt-<date>`, never silently wiped |

`<scope>` is a hash of what was inspected (repo, vault, pearl registries, thread store). A run against a
different source set gets its own history file, and an explicit `--seen-file` that already belongs to
another scope is refused: otherwise a run against another repo would mark every row "gone".

`--no-archive` skips the weekly note. `--dry-run`, `summary`, `collect`, `list` and `stats` write nothing.
Existing vault notes are never rewritten; drift in other notes is **reported** with the exact claim and
the measured value, never fixed silently.

The thread store `<vault>/09 System/Нити (реестр).md` is changed only by `add` / `close`, and only its
own row: hand-written rows and prose in that file survive. `trigger` is `date:YYYY-MM-DD` (overdue after
that day) or `event:<text>` (waits for an event); anything else is rejected at `add` time. In a cell, `|`
is written `\|` and a backslash `\\`. A row that is not exactly 7 cells is never guessed: it is listed as
"not parsed" for you to fix by hand.

## Safety properties (covered by the tests)

* Third-party text (PR titles, log lines, registry cells) is data: HTML-escaped; in Markdown the pipe, newline, **every square bracket** (so `![x](https://…)` images and `[x](…)` links stay inert text instead of being fetched or linked when the note is opened), `%%` and `<` are neutralised; backslash doubled before the pipe is escaped; control, zero-width and bidi characters removed **before** API-key-shaped strings are masked.
* A collector that raises is reported as `СБОЙ СБОРЩИКА`; it never aborts the run and never turns into an empty section.
* A row is marked *gone* in the history **only** when **all** its collectors ran cleanly (a hub-claim row needs both the vault and `gh`): an unreadable source says nothing about whether its rows were resolved.
* Row identity ignores counters that change on their own (`14 PRs`, `(123d idle)`, `17 of 18 hubs`), so a persistent row cannot look "resolved and new again" every week. A pull request is identified by its **URL**, not its title: editing a title must not make a live PR count as resolved and reset its overdue age.
* Broken wikilinks in an otherwise fresh hub become their own open row ("N hubs with broken wikilinks"), so they reach the counts, `summary --alert` and the session snapshot, not just the detail table.
* `git` runs with `--no-optional-locks` (a background reader must not make a concurrent `git add` in another session fail) and `gh` is pinned with `-R owner/name`.
* The thread store is refused (not rewritten) if it is not UTF-8; CRLF line endings and a BOM are preserved; `add`/`close` hold a lock file so two processes cannot share an id.
* `install-hint` runs no subprocess. The script never calls `claude -p`.
* Tests never resolve `Path.home()` to the real home (an autouse fixture): one early version wrote a test row into the real history file, which is why the fixture exists.

## Thresholds (provisional)

`HUB_STALE_DAYS=30`, `HEADER_GAP_DAYS=14`, `PR_STALE_DAYS=14`, `DIRTY_WORKTREE_DAYS=7`, `LIST_CAP=25`,
`STATS_MIN_DAYS=28`, `STATS_MIN_RENDERS=4`, `STATS_KEEP_SHARE=1/3`. Heuristics chosen for recall, not
calibrated against any labelled history. Change them in the script, not in the output.

## Known limits (stated, not hidden)

* **Pearl status is free text.** A row is closed only by its *leading* word (`fixed`, `closed`, `done`, `killed`, `archived`, `superseded`, `dropped`, `merged`, `implemented`, `resolved`, `applied`, `rejected`, `withdrawn`, `promoted`, `confirmed`, …). `pending [REJECTED-AS-DESIGNED …]` stays listed, with the tag shown, so you decide. The list is a heuristic.
* **Registry rows with an unescaped `|`** in their text have the wrong number of cells; rows whose first column is not a date (markup, a different format, an extra leading column) cannot be placed either. Both are listed as unreliable instead of being read with shifted columns or skipped. The repair is in the registry (escape the pipe, fix the date). On 2026-10-02 four rows of the global registry were in this state.
* A leading closing word must be a whole word: `~~FIXED~~ reopened`, `done-ish`, `merged? no` and `closed-loop …` are **not** closed.
* **Hub claims about PR counts** are compared with *this* repo's open-PR count although the vault describes many repos.
* **A pearl row is identified by its observation text** (there is no stable id in the registry). Editing that text makes the old row look "gone" and the edited one "new"; the registry rarely edits observations (updates go into `status`), but when it does, the kill-criterion share can be flattered by it.
* `NumberOfMissedRuns` may be cumulative on a laptop that sleeps; no real task has had it above 0 yet.
* **"Gone from the list" is not "closed by this tool"**: a row also leaves when someone fixed it elsewhere or the source changed. The criterion below measures whether the list tracks real work, not who did it. An overdue human PR can still be merged without the page ever being read, so even the overdue-only criterion can pass for reasons unrelated to the tool; treat a pass as "not refuted", not as proof.
* **The history is per machine and per source set.** Running from a development worktree uses that worktree's repo (its own experiments and pearl registry) and therefore a separate history; install the weekly task from the main checkout after merging.
* **Stale lock takeover** (a lock file older than 30 s) is not atomic: two processes that both see the same stale lock can both proceed. It needs a crashed holder and two simultaneous writers; accepted, single-user tool.
* **Secret masking** covers API-key shapes, JWTs, cloud keys, `user:pass@` URLs, `NAME=value` and JSON-quoted `"password": "…"` fields. It is a safety net for text copied from logs and PR titles, not a guarantee.

## Kill criterion (computed by `stats`)

The tool earns its place only if the list gets acted on. After at least 4 distinct render days over about
three weeks, `stats` takes the rows that have been **overdue** for 28+ days and prints the share that has
left the list. Only overdue rows are judged on purpose: a fresh PR or a dirty worktree closes through normal
work whether or not anyone reads the page, and counting those would let the criterion pass with nothing
acted on because of the tool.

* **keep** if at least one third left;
* **otherwise** treat the tool as provisional and remove it — a page nobody acts on is the same failure it was built to fix.

Unit of analysis: rows, not renders; a row that returns after leaving counts as new. With fewer than 4 render
days or fewer than 28 days of history the verdict is `НЕДОСТАТОЧНО ИСТОРИИ`, never a favourable one.

Status at the time of writing (2026-10-02): the tool was built the same day and has no history. **No claim of
usefulness is made.**

## Session-start summary (hook, separate change)

`hooks/threads_center_session.py` shows the last render in at most four lines when a session starts. It
runs no collectors (they take 10+ seconds); it reads `threads-center-last.json`, which `render` writes next to
the HTML page:

```json
{"version": 1, "generated": "...", "today": "YYYY-MM-DD", "status": "OK",
 "counts": {"overdue": 0, "open": 0, "waiting": 0}, "unchecked": 0, "partial": 0,
 "headline": "...", "top_overdue": [{"kind": "...", "label": "..."}],
 "note": "...", "page": "...", "scope": "..."}
```

* The hook rebuilds the headline from the numbers and never copies free text. The file itself holds only
  counts and labels of rows from local sources: a pull-request title is replaced by `PR #N (открыт N дн.)`,
  because the repo is public and a stranger can write a title; the file is shown in every session's context.
* A snapshot older than 8 days is reported as **stale**: a weekly render that silently stopped is the same
  failure the tool exists to catch. A missing file is silent (never rendered); an unreadable file is
  reported, never treated as "all clear".
* Only the renderer writes the file; `summary`, `collect` and `render --dry-run` never do, and a render that
  ends in `INSUFFICIENT_DATA` leaves the previous snapshot untouched.

## Weekly schedule (not installed automatically)

`install-hint` prints a PowerShell command that registers a Monday 07:30 task running `render` with the
current Python, with `-WorkingDirectory` set to the repo and `-StartWhenAvailable`, so a Monday on which
the laptop was off is made up when it is switched on. Creating the task is a separate, explicit decision.
