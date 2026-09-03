"""Shared data types for the wiki retrieval chain (vector_store.py, knowledge_librarian.py).

WHY: extracted 2026-09-03 during the memory-retrieval-repair spec
(docs/memory-retrieval-repair-tz.md) so both modules share one join-key contract
instead of each inventing its own string-based key (title vs stem vs a hidden
path convention) that silently drifts apart -- exactly the incident that spec's
§0.2 documents: the index stored [[Title]], and the file lookup guessed a
filename from the title -- the two agreed only by coincidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WikiRef:
    """The one join key between the vector/TF index and the file on disk.

    rel_path is POSIX-style (forward slashes), relative to WIKI_DIR --
    e.g. "projects/2026-09-02_auc_red_flags.md". title is display-only and
    must never be used as a lookup key (two files can share an H1 title).
    """

    rel_path: str
    title: str


@dataclass(frozen=True)
class SearchHit:
    """One retrieval result, tagged with how it was found.

    WHY `source` (memory-retrieval-repair-tz.md PR-4): the HOT/WARM/COLD
    tier classifier scores keyword hits by literal overlap -- a dense hit
    found by meaning alone has zero overlap and needs its similarity score
    substituted in instead, which requires knowing which kind of hit this is.
    """

    ref: WikiRef
    score: float
    source: Literal["keyword", "dense"]


@dataclass(frozen=True)
class RebuildReport:
    """Structured outcome of one rebuild_index() call.

    WHY not a bare int (memory-retrieval-repair-tz.md PR-1/PR-3): a bare
    count cannot distinguish "10 indexed, 0 failed" from "10 indexed, 5
    failed silently" -- the exact ambiguity that let 0.1-0.4 in the spec's
    ground-truth table ship behind a green test suite. `skipped`/`changed`
    make the corpus-fingerprint no-op path (PR-1) visible too, instead of
    reporting 0 indexed in a way indistinguishable from an empty wiki.
    """

    scanned: int
    indexed: int
    deleted: int
    failed: int
    skipped: int
    backend: Literal["chroma", "tf"]
    changed: bool
