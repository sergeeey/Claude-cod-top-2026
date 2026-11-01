"""Ledger closure census -- implements the frozen rules in claim.md. No other logic.

Run: python analyze.py   (reads data/pr_snapshot.json, writes data/results.json)
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

HERE = Path(__file__).parent
SNAP = json.loads((HERE / "data" / "pr_snapshot.json").read_text(encoding="utf-8"))
SNAPSHOT_TIME = datetime.fromisoformat(
    (HERE / "data" / "snapshot_time.txt").read_text(encoding="utf-8").strip().replace("Z", "+00:00")
)
START = datetime(2026, 9, 10, tzinfo=UTC)

BC_PATTERNS = [
    r"^hooks/(?!CLAUDE\.md$)",
    r"^rules/",
    r"^agents/",
    r"^commands/",
    r"^skills/.+/SKILL\.md$",
    r"^skills/registry\.yaml$",
    r"^scripts/.+\.py$",
    r"^claude-md/CLAUDE\.md$",
    r"^install\.sh$",
    r"^\.github/workflows/",
]
STRICT_PATTERNS = [r"^hooks/(?!CLAUDE\.md$)", r"^rules/", r"^scripts/(check_|gen_|sync_).+\.py$"]
LABELS = ["Change", "Prediction", "Falsified if", "Check after"]
OUTCOME_WORDS = re.compile(r"(?i)\b(confirmed|falsified|held|wrong|surprise|prediction|ledger)\b")


def is_bc(files: list[str], patterns: list[str]) -> bool:
    return any(re.search(p, f) for f in files for p in patterns)


def label_pattern(label: str) -> str:
    # Amendment 1: label starts a line, has a non-placeholder value, and is not in a table row.
    return (
        r"(?im)^(?!\s*\|)[\s>*\-•_`]*"
        + re.escape(label).replace(r"\ ", r"\s+")
        + r"\b\W{0,3}:\s*\**\s*(?!<)\S"
    )


def has_label(body: str, label: str) -> bool:
    return re.search(label_pattern(label), body) is not None


def d1(body: str) -> bool:
    return has_label(body, "Falsified if")


def d4(body: str) -> bool:
    return all(has_label(body, lb) for lb in LABELS)


def check_after_text(body: str) -> str | None:
    m = re.search(label_pattern("Check after"), body)
    if not m:
        return None
    line_end = body.find("\n", m.start())
    line = body[m.start() : line_end if line_end != -1 else len(body)]
    return line.split(":", 1)[1].strip().strip("*").strip()


def checkable(text: str | None) -> bool:
    return bool(text) and re.search(r"\d", text) is not None


def due_status(text: str | None, pr_idx: int, merged_sorted: list[dict]) -> str:
    if not text:
        return "undeterminable"
    iso = re.search(r"(20\d\d)-(\d\d)-(\d\d)", text)
    if iso:
        try:
            d = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return "undeterminable"
        return "due" if d <= SNAPSHOT_TIME.date() else "not_due"
    n = re.search(r"(?i)(\d+)\s*PRs?\b", text)
    if n:
        after = len(merged_sorted) - pr_idx - 1
        return "due" if after >= int(n.group(1)) else "not_due"
    return "undeterminable"


def main() -> None:
    prs = []
    for p in SNAP:
        merged = datetime.fromisoformat(p["mergedAt"].replace("Z", "+00:00"))
        prs.append(
            {
                "number": p["number"],
                "title": p["title"],
                "merged": merged,
                "body": p.get("body") or "",
                "files": [f["path"] for f in p.get("files", [])],
                "comments": p.get("comments", []),
            }
        )
    prs.sort(key=lambda x: x["merged"])
    window = [p for p in prs if p["merged"] >= START]
    control = [p for p in prs if p["merged"] < START]

    def tag(p: dict) -> dict:
        t = check_after_text(p["body"])
        return {
            "bc": is_bc(p["files"], BC_PATTERNS),
            "strict": is_bc(p["files"], STRICT_PATTERNS),
            "d1": d1(p["body"]),
            "d4": d4(p["body"]),
            "check_text": t,
            "checkable": checkable(t),
        }

    for p in prs:
        p.update(tag(p))

    bc = [p for p in window if p["bc"]]
    strict = [p for p in window if p["strict"]]
    declared = [p for p in window if p["d1"]]
    declared_bc = [p for p in bc if p["d1"]]

    # candidates for closure
    for p in declared:
        idx = prs.index(p)
        p["due"] = due_status(p["check_text"], idx, prs)
        cands = []
        pat = re.compile(r"#" + str(p["number"]) + r"\b")
        for q in prs[idx + 1 :]:
            if pat.search(q["body"]) and OUTCOME_WORDS.search(q["body"]):
                m = OUTCOME_WORDS.search(q["body"])
                cands.append({"where": f"PR #{q['number']} body", "word": m.group(0) if m else ""})
        for c in p["comments"]:
            created = datetime.fromisoformat(c["createdAt"].replace("Z", "+00:00"))
            if created > p["merged"] and OUTCOME_WORDS.search(c.get("body", "")):
                cands.append(
                    {
                        "where": "own comment " + c["createdAt"],
                        "word": OUTCOME_WORDS.search(c["body"]).group(0),
                    }
                )
        p["candidates"] = cands

    def share(a: int, b: int) -> str:
        return f"{a}/{b}" + (f" = {a / b:.2f}" if b else "")

    due_declared = [p for p in declared if p["due"] == "due"]
    result = {
        "snapshot_time": SNAPSHOT_TIME.isoformat(),
        "window_prs": len(window),
        "bc_prs": len(bc),
        "strict_prs": len(strict),
        "declared_d1": len(declared),
        "declared_d4": sum(1 for p in window if p["d4"]),
        "M1_declared_over_bc": share(len(declared_bc), len(bc)),
        "M1_declared_over_all": share(len(declared), len(window)),
        "M1_d4_over_bc": share(sum(1 for p in bc if p["d4"]), len(bc)),
        "M1_strict": share(sum(1 for p in strict if p["d1"]), len(strict)),
        "declared_outside_bc": [p["number"] for p in declared if not p["bc"]],
        "M3_checkable": share(sum(1 for p in declared if p["checkable"]), len(declared)),
        "due_counts": {
            k: sum(1 for p in declared if p["due"] == k)
            for k in ("due", "not_due", "undeterminable")
        },
        "due_declared_n": len(due_declared),
        "due_with_mechanical_candidate": sum(1 for p in due_declared if p["candidates"]),
        "negative_control": {
            "n": len(control),
            "d1": sum(1 for p in control if p["d1"]),
            "d1_numbers": [p["number"] for p in control if p["d1"]],
        },
        "declared_detail": [
            {
                "number": p["number"],
                "merged": p["merged"].date().isoformat(),
                "title": p["title"][:90],
                "bc": p["bc"],
                "d4": p["d4"],
                "check_after": p["check_text"],
                "checkable": p["checkable"],
                "due": p["due"],
                "candidates": p["candidates"],
            }
            for p in declared
        ],
    }
    (HERE / "data" / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "declared_detail"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
