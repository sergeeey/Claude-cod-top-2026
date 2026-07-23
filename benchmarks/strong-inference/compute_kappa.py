"""Cohen's kappa for the B6 Strong Inference inter-rater agreement data.

Source: benchmarks/strong-inference/run-2026-07-23-full.md, Sample 1/2/3 tables
(lines 246-257, 307-332, 365-372), transcribed by hand from the markdown tables.
Cross-verified against the doc's own reported raw-agreement counts (8/10, 22/24,
3/6) before trusting the transcription -- see the assert block below.
"""

from sklearn.metrics import cohen_kappa_score

C, P, INC = "CORRECT", "PARTIALLY", "INCORRECT"

# Sample 1 -- sensitivity-check population (10 items)
sample1 = [
    (INC, P),
    (C, C),
    (P, P),
    (C, C),
    (C, C),
    (C, C),
    (C, P),
    (C, C),
    (C, C),
    (C, C),
]

# Sample 2 -- original run, Tasks 3-10, all 3 arms (24 items)
sample2 = [
    (INC, INC),
    (C, C),
    (P, P),  # Task 3 A/B/C
    (C, C),
    (C, C),
    (C, C),  # Task 4 A/B/C
    (INC, INC),
    (C, C),
    (C, C),  # Task 5 A/B/C
    (C, C),
    (C, C),
    (C, C),  # Task 6 A/B/C
    (C, C),
    (C, C),
    (P, C),  # Task 7 A/B/C
    (P, C),
    (C, C),
    (C, C),  # Task 8 A/B/C
    (C, C),
    (C, C),
    (C, C),  # Task 9 A/B/C
    (C, C),
    (C, C),
    (C, C),  # Task 10 A/B/C
]

# Sample 3 -- original run, Tasks 1-2, all 3 arms (6 items)
sample3 = [
    (C, C),
    (C, P),
    (P, INC),  # Task 1 A/B/C
    (P, P),
    (C, C),
    (C, P),  # Task 2 A/B/C
]

# Sanity check: transcription must reproduce the doc's own reported raw counts
assert sum(a == b for a, b in sample1) == 8, "Sample 1 agreement != 8/10"
assert sum(a == b for a, b in sample2) == 22, "Sample 2 agreement != 22/24"
assert sum(a == b for a, b in sample3) == 3, "Sample 3 agreement != 3/6"
print("Transcription sanity check: OK (8/10, 22/24, 3/6 all match the doc)")

sample_2_3 = sample2 + sample3  # the 30-item ORIGINAL-population set MCID rests on
all_40 = sample1 + sample2 + sample3


def report(name, pairs):
    g1 = [a for a, b in pairs]
    g2 = [b for a, b in pairs]
    kappa = cohen_kappa_score(g1, g2, labels=[C, P, INC])
    raw_agree = sum(a == b for a, b in pairs) / len(pairs)
    print(f"\n{name} (n={len(pairs)}):")
    print(f"  raw agreement: {raw_agree:.4f} ({sum(a == b for a, b in pairs)}/{len(pairs)})")
    print(f"  Cohen's kappa (sklearn): {kappa:.4f}")
    # manual cross-check, independent of sklearn's implementation
    from collections import Counter

    n = len(pairs)
    po = raw_agree
    g1_counts = Counter(g1)
    g2_counts = Counter(g2)
    pe = sum((g1_counts[k] / n) * (g2_counts[k] / n) for k in set(g1_counts) | set(g2_counts))
    kappa_manual = (po - pe) / (1 - pe) if pe != 1 else float("nan")
    print(f"  Cohen's kappa (manual formula): {kappa_manual:.4f}  (Po={po:.4f}, Pe={pe:.4f})")
    print(f"  match: {abs(kappa - kappa_manual) < 1e-9}")


report("Sample 1 (sensitivity-check population)", sample1)
report("Sample 2+3 (original-run population, 30/30 -- MCID/dogfooded rests on this)", sample_2_3)
report("Grand total (all 40 items, both populations pooled)", all_40)
