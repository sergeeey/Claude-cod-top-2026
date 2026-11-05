# Protocol (frozen before runs)

Fixed commit: `bc02e1c940231316eefb5064515727c30eb0abd9`. One fresh clone per arm
(`git clone --shared`, checkout the commit). The acceptance checker is `check_t1.py`; it was
validated on six synthetic traces (correct answer, trap, one trap name, missing block, no tool
call, modified repository) before any arm ran.

## Common command

```
claude -p "$(cat tasks/T1_prompt.txt)" --model claude-sonnet-5-5 \
  --permission-mode acceptEdits \
  --allowedTools "Read" "Glob" "Grep" "Bash(python *)" "Bash(git *)" "Bash(ls *)" \
                 "Bash(grep *)" "Bash(find *)" "Bash(cat *)" \
  --strict-mcp-config --output-format stream-json --verbose \
  --no-session-persistence --max-budget-usd 2
```

Per arm, add: A `--safe-mode`; B nothing; C′ `--safe-mode --append-system-prompt-file
arms/C_prime_contract.md`; C `--safe-mode --append-system-prompt-file arms/C_prompt.md`.

Each run is limited to 15 minutes. All four arms start at the same time.

## Collected per run

Full stream-json trace; `check_t1.py` output (criteria 1–4, cost, turns, tool uses, permission
denials, cache-creation tokens, output tokens, git status).

## Order and blinding

The four arms run in parallel. The checker is mechanical, so no human or model grading is used
for T1. Because the arms are labelled in the output filenames, this pilot is **not blind**; that
does not matter for the objective criteria but is recorded as a limit.

## Deviations log

(empty at registration)
