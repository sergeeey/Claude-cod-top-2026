# decision.md — 20261014-contract-practical-value

## Verdict

- [ ] PROMOTE
- [ ] REPEAT
- [ ] REJECT
- [x] **IMPROVE** (primary analysis, frozen rule). No benefit of the contract text is established, and this design cannot detect the claimed benefit on these tasks (see the ceiling below). Not shipped.
- Sensitivity analysis (the two non-report executions excluded): the same rules give **REMOVE**.
- Hook line (`H`): **REMOVE**. Expected gain per 1 000 prompts is about 0.01 found-share in the primary analysis and 0 in the sensitivity analysis. The line appears on about 1.5 of 1 000 prompts (router measurements: 0.2 true and 1.3 false hints per 1 000), so its cost is small. REMOVE is an owner choice that the rule allows; the cost does not force it.
- ARCHIVE is not used: the question is still open for harder tasks.

Production was **not changed**. Nothing was committed by this experiment. Later edits in the same branch (the hook line removed, skill text corrected) are described under Corrections.

## What was run

- Ten synthetic tasks, six slots each: `C` twice, `F` twice, `H` once, `W` once. 60 slots, each filled by exactly one valid run.
- 11 executions ended on an API session-limit error and were re-run once with identical prompt and material (claim.md amendment). Seven of the eleven were arm `F`.
- Two executions (`x63c3`, `t02` arm `C`; `x0803`, `t03` arm `F`) finished, but their final message is a reply to a background notification, so the report is empty. They are graded as extracted (primary) and excluded (sensitivity), as the amendment states.
- Blind grading: one `opus` grader per task, given the rubric and six reports under labels R1–R6 (shuffled per task). The label-to-run key was kept in a folder the graders' instructions told them not to open. That is an instruction, not a technical barrier: graders had file tools, and whether they opened other files is not logged (see Limitations). Scores: 1 / 0.5 / 0 per planted defect, plus false findings per report. The primary share excludes the two items marked `counted: false` (`t06` P5, P6).

## Results

Δ = arm mean minus control mean of the found share, paired by task (`C` and `F` averaged over their two runs). 95 % interval: bootstrap over the ten tasks, 10 000 resamples, seed 20261014.

| Quantity | Primary (as extracted) | Sensitivity (two non-reports excluded) |
|---|---|---|
| Δ_F (contract text) | +0.008 [−0.142, +0.154] | +0.008 [0.000, +0.021] |
| Δ_H (hint line) | +0.050 [−0.008, +0.154] | +0.000 [−0.012, +0.013] |
| Δ_W (wrong contract) | +0.058 [0.000, +0.158] | +0.008 [0.000, +0.021] |
| False findings per task, F minus C | −0.05 | −0.05 |
| Tokens (in + cache-create + out), F / C | 1.65 | 1.67 |
| Output tokens, F / C | 1.49 | 1.53 |
| Wall-clock, F / C | 2.33 | 2.42 |
| Control found share, mean (headroom 1 − mean) | 0.942 (0.058) | 0.992 (0.008) |

Per-task Δ_F, primary: t01 0, t02 +0.5, t03 −0.5, t04 0, t05 +0.042, t06 0, t07 +0.042, t08 0, t09 0, t10 0.
Sensitivity: all zero except t05 +0.042 and t07 +0.042.

## Why the verdict is IMPROVE, not KEEP or REMOVE, on the primary analysis

- **KEEP is not met.** Δ_F is 0.008, its lower bound is below zero, and the token cost (1.65×) exceeds the +40 % cap in the rule.
- **REMOVE is not met by the primary interval.** Its upper bound (+0.154) is just above the 0.15 threshold of the rule. That upper bound is driven by the two empty reports: their 0 scores produce the +0.5 and −0.5 task deltas on `t02` and `t03`.
- **The design cannot detect the claimed benefit.** The control already scores 0.94 on average, so the largest gain any arm can show is 0.058 (primary) or 0.008 (sensitivity). The assumed standard deviation in claim.md (0.20) was not the observed one, and the ceiling was not anticipated. A benefit of 0.15 is impossible to show on these tasks.

On the sensitivity analysis the rule gives REMOVE: upper bound 0.021 is below 0.15 and point estimate 0.008 is below 0.05. The two analyses agree that no benefit is visible. They disagree only on the label, and the frozen rule takes the primary analysis.

## Cost

Even ignoring quality, the contract text costs about 1.65× the tokens and 2.33× the wall-clock time of the control (primary analysis; 1.67× and 2.42× in the sensitivity analysis). The quality gain that would justify it is not shown.

## Limitations

- **Ceiling.** Nine of ten tasks have a control found share of 1.0 or close to it. These tasks cannot separate the arms, so this experiment says nothing about contracts on harder work.
- **Grader calibration.** Eight of ten graders gave 1 to every planted defect in every non-empty report. The one empty report in `t02` and `t03` got 0 across the board, so the scale can give 0 and does use 0.5 in a few places (`t05` P6). Still, the uniformity limits what the scores can show.
- **Grader notes.** In `t06` the grader's note refers to "D1–D3" while the scores are on P1–P6. Those notes were not used to change any score.
- **Reference outputs in the rubrics.** Rubrics `r02`, `r03`, `r10` and others contain reference numbers. Graders scored against the key, not only against the task, which can inflate agreement.
- **No independent reviewer agent.** The task prohibited other agents, so no reviewer or skeptic checked the grades.
- **Executor deviations.** At least one executor (`xb834`) wrote intermediate files to `/tmp` despite the instruction to stay in its folder. One executor (`xdc2a`) wrote `report.md`; the tool refused the others, so for those the extracted final text is the report (`extract.py` uses `report.md` when it exists). Two final messages are notification replies.
- **Synthetic tasks, one executor model (`sonnet`), one machine.** Results do not transfer to the owner's real work without a new test.

## What would change the verdict

A new task set on which the control scores at most about 0.7 (headroom at least 0.3), a calibration check that a deliberately empty report gets 0 and a deliberately complete one gets 1 on every item, and a grader run that does not see reference outputs. That needs the owner's go and a budget decision, because it repeats the 60-execution design.

## Corrections and additions after review

These are added after the verdict above and do not change its numbers.

1. **Grader calibration was not checked.** In eight of ten tasks every non-empty report got the maximum on every planted defect. Empty reports got 0 (`t02`, `t03`), but a controlled test (a complete report must score 1, an empty one 0, under the same conditions) was not run. The data cannot separate lenient graders from easy tasks. This is the main threat to validity, and it was not in the first draft of this decision.
2. **The decision threshold was not calibrated.** `claim.md` sets MCID = 0.15 "by the owner's wish", not from data, and assumes σ = 0.20. The control ceiling (mean 0.94) was not anticipated, so KEEP was impossible by construction on these tasks. The result is "no benefit shown on easy tasks", not "contracts do not help".
3. **System value is bounded before the text question.** The router's precision in the earlier experiment (`20261014-contract-router-precision`) was about 8 % and recall about 2–3 %. A contract therefore rarely reaches the agent, even when its text is good. This limit applies before any question about the text, and it is not in the verdict above.
4. **Clarification on sensitivity.** Excluding the two empty executions left the point estimate of Δ_F unchanged (+0.008). What changed is its interval (narrowed to [0.000, +0.021]), which moved the rule from IMPROVE to REMOVE, and Δ_H (+0.050 to 0.000). The sensitivity result is more decisive against the contract, not less favourable to it.
5. **Process errors disclosed during the run.** An early count reported 39 finished executions when 11 of them were API-limit errors. A report said "exit code 0" for a pytest run that had failed, because the exit code was that of `tail`. Both were corrected in the run and are recorded here. Grades were transcribed by hand into `analyze_grades.py`, without an automated cross-check. At least one executor (`xb834`) wrote intermediate files to `/tmp` against the instruction to stay in its folder.

6. **Token counts were double counted, now corrected.** Summing usage per transcript record counted each assistant message once per content block. Counts are now taken once per message id (`stand/extract.py`; `--tokens-only` recomputed the metrics). The corrected ratios are in the table above; the earlier figures (1.77×, 1.80×) are kept in `stand/analysis_grades_output_pre-token-fix.txt`. The verdict does not change: the +40 % cap is still exceeded.
7. **Hook-line cost argument corrected.** The earlier text said the line costs one extra context line per prompt. The router emits a hint on about 1.5 prompts in 1 000, so the cost is small, and the expected gain is also about 0.01 found-share per 1 000 prompts. REMOVE is an owner choice the rule allows; the cost does not force it.
8. **Blinding was weaker than stated.** Reports that mention the contract or hints appeared in every arm, but not equally: C 4 of 20, F 8 of 20, H 2 of 10, W 6 of 10. A grader could partly infer the arm from them, and some packets also quoted run directory names. Graders were instructed not to open other files, but that was not enforced, and their tool use is not logged. Removing the reports that mention the contract (`EXCLUDE_CONTRACT_MENTIONS=1 python analyze_grades.py`) leaves 40 runs in 7 tasks: Δ_F −0.065 [−0.423, +0.214], Δ_W +0.167 [0.000, +0.500]. Every interval includes zero and the subsample is too small to conclude. The no-ship decision does not depend on this: no analysis shows the +0.15 gain, and the cost is measured. But the experiment cannot say whether contract text helps.
9. **Reruns.** The rerun prompts are identical to the originals except the run directory path (`rerun_prepare.py` asserts this). `ЗАДАНИЕ.txt` is a copy of `prompts/<id>.txt` (checked for one run); `rerun_prepare.py` writes it, The original runs' copies were made by a step not included in the stand; one checked copy equals its prompt.

Reproduction material is in `stand/` (see `stand/README.md`). Raw run folders and executor file copies are not included, for size. The personal live skill index is not published: it lists personal skills, and the repository's own policy forbids publishing that kind of index. It is kept locally (sha256 `70a46f898fb23a7bd2a2557204afeabe90d466e2b4610bb7e816d2aa483c5b68`), and `prepare_runs.py` needs it to rebuild the prompts.

## Owner decisions still open

- Whether to run the harder-task redesign. Not started.
- Whether to keep `contract` text out of the shipped router until then. Recommended: yes.
- Whether the keyword router's trigger phrases ('done when', 'критерии готовности') should be removed: they may still suggest `/contract` without the hook. Not measured.
- Whether the blind key and plan stay published (currently published after grading).
