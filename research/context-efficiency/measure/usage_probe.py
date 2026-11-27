"""Read-only probe: which usage fields exist in Claude Code session logs.

Prints only key names and aggregate counts (no message content).
"""

import glob
import json
import os
import sys
from collections import Counter

ROOT = r"C:\Users\serge\.claude\projects\D--Claude-cod-top-2026"


def main() -> int:
    files = sorted(glob.glob(os.path.join(ROOT, "*.jsonl")), key=os.path.getsize)
    print(f"jsonl files at top level: {len(files)}")
    # sample the 3 smallest and 2 largest to keep runtime bounded
    sample = files[:3] + files[-2:]
    for path in sample:
        types = Counter()
        usage_keys = set()
        usage_turns = 0
        models = Counter()
        lines = 0
        in_tok = out_tok = cr = cc = 0
        seen = set()  # WHY: dedupe by message.id, records repeat one request's usage
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                lines += 1
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                types[rec.get("type")] += 1
                msg = rec.get("message")
                if isinstance(msg, dict):
                    u = msg.get("usage")
                    mid = msg.get("id") or rec.get("uuid")
                    if isinstance(u, dict) and mid not in seen:
                        seen.add(mid)
                        usage_turns += 1
                        usage_keys |= set(u.keys())
                        in_tok += int(u.get("input_tokens") or 0)
                        out_tok += int(u.get("output_tokens") or 0)
                        cr += int(u.get("cache_read_input_tokens") or 0)
                        cc += int(u.get("cache_creation_input_tokens") or 0)
                        models[msg.get("model")] += 1
        size_mb = os.path.getsize(path) / 1e6
        print("---")
        print(f"file={os.path.basename(path)} size_MB={size_mb:.1f} lines={lines}")
        print(f"record_types={dict(types.most_common(8))}")
        print(f"assistant_usage_turns={usage_turns} models={dict(models.most_common(3))}")
        print(f"usage_keys={sorted(usage_keys)}")
        print(f"sum input={in_tok} output={out_tok} cache_read={cr} cache_creation={cc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
