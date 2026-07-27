#!/usr/bin/env python3
"""The trap artifact: a 'sentiment classifier' that scores F1=1.000.

WHY this exists: this is what an AI agent typically produces when asked to
"build and validate a classifier" in one shot. It looks like a success —
perfect score, all cases pass — but the score is a TAUTOLOGY: the test data
has the answers baked in, and the classifier just echoes them back.

Run it: `python agent_classifier.py`
You will see F1=1.000. That number is worthless, and run_trap.py proves why.
"""

# WHY: synthetic cases with the label embedded right next to the input.
# The classifier below "passes" because it never has to generalize — the
# eval set IS the training set. This is the single most common form of
# validation theater in AI-assisted development.
SYNTHETIC_CASES = [
    ("this movie was great", "positive"),
    ("absolutely loved it", "positive"),
    ("best film of the year", "positive"),
    ("terrible waste of time", "negative"),
    ("i hated every minute", "negative"),
    ("worst thing i ever saw", "negative"),
]


def classify(text: str) -> str:
    # WHY: a "model" that memorized the synthetic set. On these exact strings
    # it is perfect. On any real review it has never seen, it is a coin flip.
    lookup = {t: label for t, label in SYNTHETIC_CASES}
    return lookup.get(text, "positive")  # default guess for unseen input


def evaluate() -> None:
    correct = sum(1 for text, label in SYNTHETIC_CASES if classify(text) == label)
    total = len(SYNTHETIC_CASES)
    f1 = correct / total  # 1.0 by construction
    # WHY: this is the exact string an agent would emit and then mark [VERIFIED].
    print(f"Classifier eval on synthetic_cases: {total} cases")
    print(f"F1={f1:.3f}  precision={f1:.3f}  recall={f1:.3f}")
    print(f"All {total} cases passed. [VERIFIED-SYNTHETIC]")


if __name__ == "__main__":
    evaluate()
