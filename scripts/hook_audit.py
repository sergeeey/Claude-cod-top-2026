#!/usr/bin/env python3
"""Quick audit: compare hooks/ dir vs settings.json registrations."""

import os
import re

text = open("C:/Users/serge/.claude/settings.json").read()
registered = set()
for m in re.finditer(r"hooks/([a-z_A-Z]+)\.py", text):
    registered.add(m.group(1))

existing = set()
for f in os.listdir("hooks"):
    if f.endswith(".py") and f != "utils.py":
        existing.add(f.replace(".py", ""))

not_registered = existing - registered
registered_missing = registered - existing

print("=== NOT REGISTERED (hooks/ exists, settings.json absent) ===")
for h in sorted(not_registered):
    print(f"  - {h}")
print()
print("=== REGISTERED BUT NOT IN WORKTREE hooks/ ===")
for h in sorted(registered_missing):
    print(f"  - {h}")
print()
print(f"Registered: {len(registered)} | In hooks/: {len(existing)}")
