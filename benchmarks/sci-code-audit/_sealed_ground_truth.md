SEALED — for adjudication only. Not shown to Arm A or Arm B.

| Packet | Verdict | Bug type |
|---|---|---|
| R1 | BUGGY | (2) Missing invariant/assertion -> bad data through undetected |
| R2 | CLEAN | -- |
| R3 | BUGGY | (3) Control/data provenance -- train/test leakage |
| R4 | BUGGY | (1) Silent fallback masking a real error |
| R5 | CLEAN | -- |
| R6 | BUGGY | (4) Undocumented reproducibility gap |

### R1 -- astropy FITS_rec.__setitem__ -- BUGGY (type 2)
Fix commit: 5eed3fbd87add4ae605806e3855aac7bd497a6c6 (PR #19404)
Bug: isinstance(key, slice) branch has two defects: (a) negative indices
silently clamped via max(0, key.start or 0) instead of resolved relative to
len(self) -- data[-2:]=rows silently writes to rows 0,1 instead of the last
two; key.step is ignored entirely; (b) no length invariant -- 
end=min(end, start+len(value)) silently truncates on a length mismatch
instead of raising, unlike NumPy's own ValueError. Fix: slice.indices(len(self))
+ zip(..., strict=True). Credit: flagging either defect = hit; both = full hit.

### R2 -- scikit-learn KFold -- CLEAN
Bait: random_state=None (looks like a reproducibility gap; is documented,
intended contract, and __init__ explicitly rejects random_state when
shuffle=False). Bait: this IS a CV splitter (leakage-hunting target); folds
are provably disjoint (fold_sizes sums to n_samples, current advances
monotonically, no overlap). shuffle() operates on a local np.arange copy,
never X itself -- no aliasing. Any HIGH/MEDIUM finding here = false positive.

### R3 -- sktime Imputer -- BUGGY (type 3)
Fix commit: 88c947a240b0b92658a7723a51a3bd2b9e8efb33 (PR #2382)
Bug: "fit_is_empty": True means NO _fit at all -- every statistic (mean,
median, random bounds, drift/forecaster fit) is computed from the data
passed to transform(), which in a CV/forecasting pipeline is the TEST set.
Real train/test information leakage, inflates held-out scores. Fix: fit_is_empty
-> False, real _fit stores self._mean/_median/self._X, _transform consumes
fit-time stats. Secondary legit finding in same PR: _check_method had no
allow-list validation of `method` (a nonexistent method silently never fired
because example data had no NaNs) -- credit separately if found, leakage is primary.

### R4 -- pandas raise_parser_error -- BUGGY (type 1)
Fix commit: 210fea9d4dc4314f9bc4ddb5f7dab6fa87912ca9 (PR #13693)
Bug: when the C tokenizer's read() callback into Python raises (e.g.
UnicodeDecodeError on a Shift-JIS file), the real pending Python exception
is silently discarded and raise_parser_error() always raises a generic
CParserError("Error tokenizing data...") instead -- true cause and traceback
lost. Fix: check PyErr_Occurred() first, re-raise the original exception via
PyErr_Fetch before falling back to the generic message.

### R5 -- CPython statistics.covariance/correlation -- CLEAN
Bait: try/except ZeroDivisionError -> raise StatisticsError is the same
syntactic shape as a "silent fallback" bug but is the OPPOSITE -- converts a
cryptic error into a loud, specific, correctly re-raised one. Flagging this
as a defect = false positive (missing `from None`/`from exc` chaining is a
style note, not a trust defect -- don't score as a hit). Both functions have
the exact invariants R1 was missing (length check, min-sample check,
method allow-list). Any HIGH/MEDIUM finding here = false positive.

### R6 -- AllenNLP MultiprocessDatasetReader._instances -- BUGGY (type 4)
Fix commit: 20772152f930f9e34126083dc966911ef03d6414 (PR #2729)
Bug (two compounding sources of nondeterminism, undocumented): (a) Python's
`random` module is NOT deterministically reseeded across spawned processes --
random.shuffle(shards) ignores any seed set in the parent process, shard
order differs on every "seeded" run; (b) glob.glob(file_path) order is
filesystem-dependent/unspecified -- even a correctly-seeded shuffle of a
differently-ordered input list gives a different result. Fix: shards.sort()
before shuffling + switch random.shuffle -> np.random.shuffle (numpy IS
process-safe for this) + explicit docstring scoping residual nondeterminism
(worker interleaving) rather than claiming full determinism. Credit: the
random-reseeding issue is primary; unsorted glob is a genuine separate
finding; documented-scope gap is a lesser third finding.

Scoring shape: recall measured on R1/R3/R4/R6, false-positive rate on R2/R5.
"Clean" on R2/R5 is [INFERRED] (no known defect of the 4 target types found
after real review), not [VERIFIED] absolute correctness -- if a reviewer
surfaces a genuine, previously-unknown defect there, treat it as a dataset
finding, not automatically a false positive.
