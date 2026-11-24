import json

TRANSCRIPT = r"C:\Users\serge\.claude\projects\D--Claude-cod-top-2026\29a715b1-3478-43c8-b908-635a18c4834e.jsonl"
marker = "Blind skeptic falsification of in-toto Gate 10 claim"

with open(TRANSCRIPT, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

tool_use_id = None
for i, raw in enumerate(lines):
    if marker in raw:
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        content = obj.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == "Agent"
                ):
                    print("FOUND tool_use at line", i + 1, "id=", block.get("id"))
                    tool_use_id = block.get("id")

print("tool_use_id=", tool_use_id)
if tool_use_id:
    count = 0
    for i, raw in enumerate(lines):
        if tool_use_id in raw:
            obj = json.loads(raw)
            content = obj.get("message", {}).get("content", [])
            print("line", i + 1, "type of content:", type(content))
            print(json.dumps(content, ensure_ascii=False)[:800])
            print("---")
            count += 1
            if count > 3:
                break
