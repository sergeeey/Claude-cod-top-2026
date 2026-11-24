import hashlib, pathlib, datetime, json
root = pathlib.Path(".")
files = sorted([p for p in root.glob("tasks/**/*") if p.is_file()] + list(root.glob("statements/*.txt")) + list(root.glob("_r/r*.json")) + [root / "prepare_runs.py", root / "live_index.json"])
lines = ["# frozen " + datetime.datetime.now(datetime.timezone.utc).isoformat()]
for f in files:
    lines.append(hashlib.sha256(f.read_bytes()).hexdigest() + "  " + str(f).replace("\\", "/"))
pathlib.Path("frozen_tasks.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(len(files), "files hashed")
