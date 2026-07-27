#!/usr/bin/env python3
"""anonymize_for_grading.py -- MANDATORY blind-grading step, added after an
independent review (2026-07-27) correctly flagged that the original design let
the same person/session both select the pilot task AND grade catch/no-catch
against A/B/C labels -- a self-referential bias risk on top of the
already-acknowledged task-selection bias (see estimand.md L4). Without this
step, a grader who knows "this is Copy C, the config I built" could
consciously or not read its output more charitably.

Takes the 3 raw logs from a run_pilot_task.sh run, copies them under random
anonymized names (Output_1/2/3) into logs/<task_id>/blind/, and writes the
real mapping to logs/<task_id>/blind_mapping.json. The grader reads ONLY the
Output_N files and records catch/no-catch per N -- never opens
blind_mapping.json until after recording grades (score_pilot.py --blind mode
handles the reveal+translation automatically, so the grader never needs to).

Usage:
  python anonymize_for_grading.py --task-id positive-control
"""

import argparse
import json
import random
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
LOG_ROOT = EXPERIMENT_DIR / "logs"

COPY_FILES = {
    "A": "A_vanilla.txt",
    "B": "B_minimal.txt",
    "C": "C_standard.txt",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument(
        "--seed", type=int, default=None, help="omit for a fresh random shuffle each call"
    )
    args = ap.parse_args()

    task_log_dir = LOG_ROOT / args.task_id
    if not task_log_dir.exists():
        raise SystemExit(f"No logs found at {task_log_dir} -- run run_pilot_task.sh first")

    blind_dir = task_log_dir / "blind"
    blind_dir.mkdir(exist_ok=True)
    mapping_file = task_log_dir / "blind_mapping.json"
    if mapping_file.exists():
        raise SystemExit(
            f"{mapping_file} already exists -- a blind mapping for this task was already "
            "generated. Delete it manually first if you really want to re-shuffle (but "
            "note: re-shuffling after a grader has already seen the first shuffle "
            "defeats the point of blinding)."
        )

    copies = list(COPY_FILES.keys())
    rng = random.Random(args.seed)
    rng.shuffle(copies)
    mapping = {}  # anonymized label -> real copy letter
    for i, copy_letter in enumerate(copies, start=1):
        src = task_log_dir / COPY_FILES[copy_letter]
        if not src.exists():
            raise SystemExit(f"Expected log file missing: {src}")
        dst = blind_dir / f"Output_{i}.txt"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        mapping[f"Output_{i}"] = copy_letter

    with open(mapping_file, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"Wrote anonymized outputs to {blind_dir}/ (Output_1.txt, Output_2.txt, Output_3.txt)")
    print(f"Real mapping saved to {mapping_file} -- DO NOT open this until grading is recorded.")
    print("\nNext: read Output_1.txt / Output_2.txt / Output_3.txt in the blind/ folder,")
    print("grade each against the pre-registered criterion, then run:")
    print(
        f'  python score_pilot.py --task-id {args.task_id} --criterion "<criterion>" '
        "--blind --catch-1 <0|1> --catch-2 <0|1> --catch-3 <0|1>"
    )


if __name__ == "__main__":
    main()
