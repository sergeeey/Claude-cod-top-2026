"""Read-only: startup context footprint per session from first assistant usage record.

For each top-level session log, take the FIRST assistant message that carries
usage and report its input-side tokens (fresh input + cache creation + cache read).
Stops reading each file after the first usage record, so it stays cheap.
Prints aggregates only; no message content.
"""

import glob
import json
import os
import statistics
import sys

ROOT = r"C:\Users\serge\.claude\projects\D--Claude-cod-top-2026"


def first_usage(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message")
            if rec.get("type") != "assistant" or not isinstance(msg, dict):
                continue
            u = msg.get("usage")
            if not isinstance(u, dict):
                continue
            return {
                "ts": rec.get("timestamp"),
                "model": msg.get("model"),
                "input": int(u.get("input_tokens") or 0),
                "cache_create": int(u.get("cache_creation_input_tokens") or 0),
                "cache_read": int(u.get("cache_read_input_tokens") or 0),
                "output": int(u.get("output_tokens") or 0),
            }
    return None


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "*.jsonl")), key=os.path.getmtime)
    rows = []
    for p in files:
        r = first_usage(p)
        if r:
            r["file"] = os.path.basename(p)[:8]
            r["startup_in"] = r["input"] + r["cache_create"] + r["cache_read"]
            rows.append(r)
    print(f"sessions with usage: {len(rows)} of {len(files)} top-level files")
    for r in rows:
        print(
            f"{r['ts'] or '-':<26} {r['file']} {str(r['model']):<22} "
            f"in={r['input']:>6} cc={r['cache_create']:>6} cr={r['cache_read']:>7} "
            f"startup_in={r['startup_in']:>7} out={r['output']:>5}"
        )
    vals = [r["startup_in"] for r in rows]
    if vals:
        print(
            f"startup_in: n={len(vals)} median={statistics.median(vals):.0f} "
            f"min={min(vals)} max={max(vals)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
