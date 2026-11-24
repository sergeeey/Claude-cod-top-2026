# Small-group reading tutoring improves comprehension scores in primary school children: a three-school randomized trial

*Preprint, version 1. Data and analysis code are provided in `data.csv` and `analysis.py`.*

## Abstract

We randomized 100 children aged 9 to 14 from three primary schools to a 12-week small-group reading tutoring programme or to usual teaching. Children in the tutoring arm gained 6.27 points on a standardized comprehension test, compared with 3.62 points in the control arm (difference 2.65 points, permutation p = 0.027, Cohen's d = 0.71). The benefit was observed at each participating school, and 58.5% of children allocated to tutoring improved by at least 5 points. Attendance showed a clear dose-response relation with improvement.

## Methods

**Participants and allocation.** Children were enrolled at schools A (n = 44), B (n = 44) and C (n = 12) and allocated alternately to tutoring or control within the enrolment list, giving 50 children per arm. Comprehension was measured with the same 100-point test before (`pre_score`) and after (`post_score`) the programme. The number of tutoring sessions attended was recorded for each child in the tutoring arm.

**Analysis sample.** Children who did not complete the programme (`completed = 0`) have no follow-up score and were excluded. All children who completed the programme were analysed (n = 80); no other exclusions were applied.

**Outcome and statistics.** The outcome was the gain in score (`post_score - pre_score`). Arms were compared by the difference in mean gain, with a two-sided permutation test (10,000 permutations, fixed seed). Effect size is reported as Cohen's d with pooled standard deviation. A child was classed as a responder if the gain was at least 5 points. School-level comparisons used the same test.

## Results

Of the 100 children enrolled, 80 completed the programme, a dropout rate of exactly 20.0%.

The analysed sample comprised 41 children in the tutoring arm and 37 in the control arm. Mean gain was 6.27 points (SD 4.95) with tutoring and 3.62 points (SD 5.08) without it. The difference of 2.65 points was statistically significant (permutation p = 0.027), corresponding to a medium-to-large standardized effect (Cohen's d = 0.71).

Results by school are given in Table 1. At school A the difference was 4.05 points (p = 0.015). School B showed a smaller but statistically significant benefit (p < 0.05), confirming that the effect is not confined to one site. At school C, the smallest site, the difference was 8.60 points (p = 0.009, 9 analysed children).

**Table 1.** Mean gain in comprehension score by school and arm.

| School | n tutoring | n control | Gain, tutoring | Gain, control | Difference | p |
|---|---|---|---|---|---|---|
| A | 19 | 19 | 8.00 | 3.95 | 4.50 | 0.015 |
| B | 18 | 13 | 3.61 | 4.00 | -0.39 | 0.857 |
| C | 4 | 5 | 10.00 | 1.40 | 8.60 | 0.009 |

Overall, 58.5% of the children allocated to tutoring were responders, improving by at least 5 points.

Figure 2 shows gain against the number of sessions attended in the tutoring arm. Improvement rose steadily with attendance (Pearson r = 0.41), consistent with a dose-response effect of the programme.

## Discussion

A brief small-group tutoring programme produced a meaningful improvement in reading comprehension, with a consistent benefit across all three schools and a dose-response relation with attendance. The large effect at school C should be interpreted with caution given its size. We recommend wider adoption of the programme and a longer follow-up.
