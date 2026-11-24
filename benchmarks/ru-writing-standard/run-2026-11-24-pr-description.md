# ru-writing-standard: one rewrite, scored by a fixed checker

**Date:** 2026-11-24. **n = 1.** Run by the author's assistant, scored by a script the same
assistant wrote before the rewrite existed. Marker: `[VERIFIED-SYNTHETIC]`.

## Question

Does a rewrite that follows `skills/extensions/ru-writing-standard/SKILL.md` remove the
template phrases the skill names, keep every fact, and stay short, on a text that has all
three problems?

## Input

`original.txt` is a Russian PR description written for this run in the template style the
skill describes. The facts in it are real (PR #550: `_sealed_ground_truth.md` untracked,
3 files, +8/-77, CI green, key still in public history). The wording is invented, so this is
not a text anyone sent. That is the main limit of this run.

## Pre-registered checks (`check_rewrite.py`, written before `rewrite.txt` existed)

1. None of 8 template phrases appears (the 6 named in section 1 of the skill, plus
   "в рамках данного" and "комплексн" from the skill's own PR example).
2. Six facts are kept: `_sealed_ground_truth.md`, "3 файла", "+8", "77", "истори", "CI".
3. No number appears that was not in the original.
4. The rewrite is at most 0.6 of the original length.
5. The first sentence does not open with a preamble ("важно", "следует", "в рамках").

## Result

| Text | Checks passed | Detail |
|---|---|---|
| `original.txt` (negative control) | 2 of 5 | fails 1, 4 and 5, as it must |
| `rewrite.txt` | 5 of 5 | length ratio 0.43 |

The control matters: the checker is able to fail, and it did fail on the unrewritten text.

## What this does NOT show

- It does not show the rewrite reads better. The checker counts phrases, facts and length,
  not quality.
- It does not show the skill beats rewriting without it. There was no baseline arm. Template
  phrases are listed in the skill itself, so any rewrite that read the list would pass check 1.
- The input is invented prose, not a text the user took out of chat.
- The skill was called 112 times in the 60 days before this run (a scan of the author's local
  session transcripts on 2026-11-24, which cannot be reproduced from this repo), but none of
  those calls recorded whether the text it produced was good.

## Status decision

`maturity` stays `described`. Promotion to `dogfooded` needs a real text the user actually used,
graded against a bar written before the rewrite. This run is recorded as evidence only. The next
step is to pick one real outgoing text (a letter, a README section, a PR body), fix the checks,
then rewrite and score it.
