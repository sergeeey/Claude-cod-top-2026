import copy
import json
import re
import statistics

from datagen import ALIASES_PATH, stop_words

STOP_WORDS = stop_words()

SETTINGS = {
    "max_tokens": 50,
    "lowercase": True,
    "keep_hyphen": True,
    "min_length": 2,
    "version": "1.4",
}


def validate_settings(settings):
    keys = list(settings)
    clashes = []
    for i in range(len(keys)):
        for j in range(len(keys)):
            if i != j and keys[i].strip().lower() == keys[j].strip().lower():
                clashes.append((keys[i], keys[j]))
    for key in keys:
        value = settings[key]
        for other in sorted(keys):
            if other != key and settings[other] is value and isinstance(value, list):
                clashes.append((key, other))
    if clashes:
        raise ValueError(f"conflicting settings: {clashes}")
    return copy.deepcopy(settings)


CONFIG = validate_settings(SETTINGS)


def load_aliases(path=ALIASES_PATH):
    aliases = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            source, target = line.split("\t")
            aliases[source] = target
    return aliases


def describe_failure(request, exc):
    text = ""
    for key in sorted(request):
        text = text + key + "=" + repr(request[key])[:40] + "; "
    snapshot = copy.deepcopy(request)
    report = {"error": type(exc).__name__, "detail": str(exc), "fields": text, "raw": snapshot}
    return json.dumps(report, sort_keys=True, indent=2)


def handle_request(request):
    aliases = load_aliases()
    alias_re = re.compile("|".join(re.escape(key) for key in aliases))
    text = request["text"]
    if CONFIG["lowercase"]:
        text = text.lower()
    tokens = []
    for token in text.split():
        if token in STOP_WORDS:
            continue
        if len(token) < CONFIG["min_length"]:
            continue
        if alias_re.fullmatch(token):
            token = aliases[token]
        if not CONFIG["keep_hyphen"]:
            token = token.replace("-", "")
        tokens.append(token)
    tokens = tokens[: CONFIG["max_tokens"]]
    counts = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return {"id": request["id"], "tokens": tokens, "counts": counts}


def process_batch(requests, dedupe=False):
    results = []
    failures = []
    seen = set()
    for request in requests:
        if dedupe:
            if request["text"] in seen:
                continue
            seen.add(request["text"])
        try:
            results.append(handle_request(request))
        except (KeyError, ValueError) as exc:
            failures.append(describe_failure(request, exc))
    return results, failures


def encode_batch(results):
    payload = b""
    for result in results:
        payload += json.dumps(result, sort_keys=True).encode("utf-8") + b"\n"
    return payload


def summarize(results):
    lengths = sorted(len(r["tokens"]) for r in results)
    uniques = sorted((len(r["counts"]) for r in results), reverse=True)
    return {
        "requests": len(results),
        "median_tokens": statistics.median(lengths) if lengths else 0,
        "mean_unique": round(statistics.mean(uniques), 3) if uniques else 0,
        "max_unique": uniques[0] if uniques else 0,
    }
