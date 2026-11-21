# Context efficiency: does a compact startup context reduce full cost? (INVESTIGATION, v2)

Date: 2026-11-21. Branch `feat/data-analysis-discovery-protocol`, HEAD `17a92de`. Read-only mission. No paid sessions run. No global config changed. Nothing committed or pushed. Results live in the untracked folder `research/context-efficiency/`.

## Verdict

**READY_FOR_AB_TEST**, with a precise scope:

| Part | Status |
|---|---|
| Per-turn token readers (input, output, cache_create, cache_read) | ready and verified on 41 session logs |
| Per-category context breakdown | ready (`get_usage` context categories) |
| Cost counter | `cost-state` exists but does NOT reconcile with per-turn sums, so it is not yet the authoritative cost source |
| Arm A (current full context) | defined and measured |
| Arm B (compact pointer) | NOT built |
| Arm C (minimal config) | NOT defined: `--bare` changes enforcement, not only context |
| Task set with independent tests | NOT built |
| Benefit on quality or cost | NOT established. History cannot give a causal comparison. |

## 1. What loads at startup, and how it is classified

Three categories, because the path-scoped rules are not startup-loaded:

| Category | Items (bytes measured with `wc -c`) | Marker |
|---|---|---|
| **Always loaded** | global `CLAUDE.md` 7 386; 15 global rules 112 395 total (`estimand-ops` 18 949, `memory-protocol` 19 903, `doubt-driven-development` 12 838, `artifact-provenance-gates` 9 481, `skeptic-triggers` 8 599); project `CLAUDE.md` 9 562; project `.claude/rules` 9 785; `MEMORY.md` index 16 299 | [VERIFIED] (verbatim in session context) |
| **Hook-loaded** | `activeContext.md`: 37 762 B on disk, first 6 000 B injected at SessionStart. `hook_triggers.jsonl`: 579 `session_start` entries with `bytes_loaded` (typical 6 016 B) | [CODE] + [VERIFIED] telemetry |
| **Path-scoped (auto-injected when a matching file is read)** | `falsification-ladder.md` 44 910; `research-methodology.md` 52 373; `meta-loop.md` 25 996; `rationalizations.md` 11 618; `perelman-audit.md` 6 323; `coding-style.md` 1 558; `testing.md`. Frontmatter `paths:` (e.g. `experiments/**`) | [VERIFIED] (frontmatter read) |
| **On demand** | `rules-cold/*` appendices | [VERIFIED] |

Always-loaded instruction text: about 150 KB in bytes (sum of the first two rows, with the 6 000 B of `activeContext`).

## 2. Measured token share of the startup context (not estimated)

`get_usage` (context categories, this session, one snapshot):

| Category | Tokens | Share of window |
|---|---|---|
| Memory files (CLAUDE.md, rules, MEMORY) | 47 087 | 5% |
| MCP tools | 27 825 | 3% |
| System tools | 19 177 | 2% |
| System prompt | 12 157 | 1% |
| Skills | 9 920 | 1% |
| Messages (this conversation so far) | 115 928 | 12% |
| Total | 242 758 | 24% |

Checks:
- The memory-files slice (47 087 tokens) is inside the bound from bytes. At 3–4 bytes per token that bound is about 40–50k, so the byte estimate was right.
- Instruction text (memory) is about 19% of the measured non-message startup footprint (47k of about 247k), so the memory slice is not the biggest block.
- MCP tools + system tools + skills = 57 081 tokens, which is more than the memory slice. Those are harness and config levers, not CLAUDE.md levers.

Snapshot caveat: `get_usage` is a single current-session reading. It is not aggregated across sessions. The first-turn startup footprint (section 3) was measured in another session, so the two are not directly reconciled.

## 3. Startup footprint over time (first assistant turn)

| Period / sessions | Model family | Startup tokens (range) |
|---|---|---|
| 2026-05 to 2026-06 | sonnet-4-6 | 40 k – 91 k |
| 2026-08 to 2026-10 | sonnet-5 / opus-5 / sonnet-5-5 | 115 k – 214 k |
| 2026-10 to 2026-11 (incl. this session, 189 168) | haiku-5-5 | 133 k – 199 k |

[VERIFIED] The footprint grew about 3–5× from May to November. Cause [INFERRED, not isolated]: model family changed and so did the instruction set.

## 4. Before/after evidence in the history

**Global `CLAUDE.md` compaction (2026-11-18):** `CLAUDE.md.bak-compact-20261118` is 21 854 B; the current file is 7 386 B. That is a 66% reduction in that file. [VERIFIED by `wc -c`]. It is not the "300 KB → 2 KB" event from the brief: no such pair was found in the repo.

**Scheduled runs (fixed start minutes 00:47/00:57/01:15/02:03), grouped by a hash of the first user prompt:**

| Prompt group | n | Startup median before 2026-11-17 | after | Turns median |
|---|---|---|---|---|
| abdc5a3742 | 2 | 150 246 | – | 56 |
| 46ab9f0a8c | 2 | 149 702 | – | 32.5 |
| d441f72888 | 4 | 148 890 | 135 201 (−9%) | 4 |

Only one group has both sides. This is **descriptive only**: several changes landed together and no success label exists.

## 5. Full cost picture including subagents

Source: `results/followup.txt`. All top-level sessions plus subagent transcripts (624 subagent files).

| Metric | Value |
|---|---|
| Total turns | 101 409 |
| Total input | 3 784 749 |
| Total output | 115 245 975 |
| Total cache_create | 1 277 946 654 |
| Total cache_read | 46 984 923 672 |

Subagents change the totals materially, e.g. `29a715b1`: cache_read 5.08 B main-only → 5.85 B with subagents; `3cc01ee2`: 17.06 B → 17.49 B. Earlier per-file totals were lower bounds, as stated in v1.

Cache reads are priced far below fresh input. A token effect (ΔS × turns) is therefore **not** a cost effect. Any cost claim must weight by price.

## 6. `cost-state` does not reconcile: not authoritative yet

| Session | per-turn cache_read | cost-state cache_read | cost-state USD (last) |
|---|---|---|---|
| `9f84093e` | 2 640 400 056 | 322 152 703 | 83.01 |
| `53469bad` | 1 939 854 593 | 53 235 467 | 9.56 |
| `f6882b15` | 195 854 655 | 81 702 740 | 14.54 |
| `f6737287` | 10 275 027 | 8 913 638 | 3.25 |

[CONFLICTING] `cost-state` covers a different scope than the per-turn records (possibly per segment or per model, not measured here). Until the scope is confirmed, the A/B must record both: per-turn usage and `cost-state`, with USD computed from per-turn tokens × the official price of the chosen model [UNKNOWN until checked on the pricing page].

## 7. Why history is not a causal comparison

| Confound | Effect |
|---|---|
| Model switches inside one file (`3cc01ee2`: fable-5-1, haiku, opus, sonnet) | model not held fixed |
| No task label, no success label | quality not comparable |
| Instruction set changed over the period | baseline drift |
| No config flag per session | arm membership unknown |
| Subagent usage was excluded in v1 | fixed in section 5 |

Result: history gives the footprint and the cost structure, not the effect of context on success. **Benefit: INCONCLUSIVE.**

## 8. Arms

| Arm | Definition | Status |
|---|---|---|
| A full | current global + project CLAUDE.md, all always-loaded rules, MEMORY index, activeContext hook | measured, 130–215 k startup |
| B compact pointer | short root CLAUDE.md with pointers; memory-file slice on demand | NOT built. Safety-tier rules (autonomy-budget Red/Black, private-material, submission gate) must stay always-on or move into hooks. Otherwise guarantees weaken and B is invalid. |
| C minimal config | `--bare` or `--setting-sources` | NOT usable as-is: `--bare` skips hooks and CLAUDE.md auto-discovery, so it changes enforcement as well as context. Needs one permitted dry run to confirm which CLAUDE.md sources are skipped [UNKNOWN] |

B and C use the same model, the same tools and the same task set, with the same success criteria. Those three conditions are the mission's requirement and are not yet satisfiable without building B and the tasks.

## 9. Recommendation (decision on further development)

1. **Do not pursue a general "compact CLAUDE.md" as the main lever.** The memory-file slice is 47k tokens per turn. Even removing all of it leaves MCP tools (27.8k), system tools (19.2k) and skills (9.9k) untouched, and those are larger together.
2. **Measure the harness slices first, as a separate question.** MCP tool exposure and skill exposure are the bigger blocks. Changing them is a config change, so it needs the owner's approval; this mission does not change config.
3. **If the owner approves a paid A/B,** narrow it to the memory-file slice only (arm A vs arm B with the safety-tier rules kept in the prefix). Use 6 fixed tasks, 3 repetitions, 36 sessions, and record per-turn usage and `cost-state` side by side.
4. **Cost of that A/B:** the median session is about 52 turns, with cache_read per turn around 205 k. That is on the order of 10⁷ cache-read tokens per session, so 36 sessions is roughly 10⁸–10⁹ cache-read tokens. USD is [UNKNOWN] until the pricing page is checked.

Next step that needs a yes from the owner: approval for the paid A/B on the memory-file slice, or a decision to park the idea until the MCP and skills slices are measured.

## 10. Open items

| Item | Status |
|---|---|
| `cost-state` scope | [CONFLICTING], section 6 |
| `--setting-sources` / `--bare` effect on CLAUDE.md discovery | one permitted dry run [UNKNOWN] |
| Model prices for USD | [UNKNOWN], not checked |
| "300 KB → 2 KB" pair | not found; closest is `CLAUDE.md` 21 854 → 7 386 B |
| Token counting for instruction text | not run (would be a paid external call); memory slice is measured via `get_usage` instead |

## Files

- `measure/usage_probe.py`, `measure/startup_footprint.py`, `measure/session_totals.py`, `measure/followup.py`: read-only, aggregates and hashes only, no message content.
- `results/usage_probe.txt`, `results/startup_footprint.txt`, `results/session_totals.txt`, `results/followup.txt`: outputs from 2026-11-21.
- All four measurement scripts are copied into `measure/` and reproduce the results above.
