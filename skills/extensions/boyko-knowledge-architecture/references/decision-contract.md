# Adaptive decision contract

## Core distinction

- **Source material:** original messages, papers, raw datasets, code, signed documents.
- **Claim ledger:** canonical record of a claim and its truth/evidence/protocol status within defined scope.
- **Run log:** a measured execution with command, environment, inputs, version, exit code and outputs.
- **Derived index/view:** search or presentation projection; may cache fields but must not become independent authority.
- **Agent memory:** retrieval hints and context; not verified factual authority.
- **Backup:** recovery copy with tested restore; not independent source of truth.

Multiple physically separate stores are acceptable if their ownership is unambiguous. More than one status field is acceptable if dimensions are semantically independent and schema-defined. The anti-pattern is unsynchronized independent *writers* for the same semantic fact.

## Comparative decision test

For a proposed change, record:
- `current_capability`: what existing system demonstrably does
- `failure`: exact reproducible gap, or `UNKNOWN`
- `proposal`: smallest reversible repair
- `alternative`: keep current mechanism and document limitation, or another lower-cost remedy
- `benefit`: concrete observable improvement
- `cost`: migration, maintenance, dependencies and privacy exposure
- `rollback`: exact recovery route and verification
- `decision`: KEEP / IMPROVE / LINK / ARCHIVE / RETIRE

No migration solely because a new framework is fashionable. No external sync of confidential material without specific permission. No deleting source records on inferred equivalence.

## Retrieval task contract

Prompt a fresh agent to answer one bounded question whose source already exists; do not tell it the file path. Require it to show which source governed the answer and where its evidence came from. Compare against a pre-registered oracle. Score only actual grounded retrieval, not plausible prose.

## Evidence freshness

Changing a code hash invalidates a *run-to-code binding*, not the underlying mathematical theorem. A deleted file may mean provenance is incomplete; it does not show the claim false. A new successful run is not independent mathematical verification if the oracle shares the flawed implementation. Model these states separately.

## Stop rule

If tests support the current architecture and no important gap remains, output KEEP and stop. The expected human burden of operating the fix must be lower than the burden it removes.
