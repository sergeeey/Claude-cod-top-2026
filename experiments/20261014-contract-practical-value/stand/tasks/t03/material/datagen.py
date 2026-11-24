import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ALIASES_PATH = os.path.join(HERE, "aliases.tsv")
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _word(rng, low=3, high=9):
    return "".join(rng.choice(LETTERS) for _ in range(rng.randint(low, high)))


def vocabulary(seed=7, size=3000):
    rng = random.Random(seed)
    words = []
    seen = set()
    while len(words) < size:
        word = _word(rng)
        if word not in seen:
            seen.add(word)
            words.append(word)
    return words


def stop_words(seed=5, count=400):
    rng = random.Random(seed)
    return rng.sample(vocabulary(), count)


def write_aliases(path=ALIASES_PATH, seed=11, count=400):
    vocab = vocabulary()
    rng = random.Random(seed)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for _ in range(count):
            fh.write(f"{rng.choice(vocab)}\t{rng.choice(vocab)}\n")
    return path


def make_requests(n=1200, seed=42, length=60):
    vocab = vocabulary()
    rng = random.Random(seed)
    requests = []
    for i in range(n):
        words = [rng.choice(vocab) for _ in range(length)]
        if i % 7 == 0:
            words.insert(rng.randint(0, len(words)), "re-" + rng.choice(vocab))
        if i % 5 == 0:
            words[0] = words[0].upper()
        requests.append({"id": i, "text": " ".join(words)})
    return requests
