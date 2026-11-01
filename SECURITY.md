# Security Policy

### Reporting a Vulnerability

If you discover a security vulnerability in this project, **please do not open a public issue**.

Instead, report it privately:

1. **Email**: Open a [private security advisory](https://github.com/sergeeey/Claude-cod-top-2026/security/advisories/new) on GitHub
2. **Or**: Contact maintainer **sergeeey** directly via GitHub

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact (what an attacker could achieve)
- Suggested fix (if you have one)

### Response Timeline

- **Acknowledgment**: within 48 hours
- **Assessment**: within 7 days
- **Fix**: critical issues within 14 days, others in next release

### Scope

This project is a configuration framework for Claude Code. Security-relevant areas include:

| Area | Risk | Example |
|------|------|---------|
| **PII Redaction hooks** | Data leakage | Bypass of masking in `redact.py` |
| **install.sh** | Code execution | Injection via crafted file paths |
| **settings.json** | Hook bypass | Disabling security hooks silently |
| **MCP profiles** | Data exfiltration | Malicious MCP server config |
| **Symlink mode** | Privilege escalation | Symlink following outside repo |

### Security Design Principles

This project follows these security principles by design. Each is marked with
whether an automated gate actually enforces it — an absolute claim that nothing
checks is a wish, not a property, and this file is what a reader uses to decide
whether to trust the install.

**Enforced — an absolute claim here is backed by a gate you can run:**

- **No external dependencies in hooks** (stdlib-only Python) —
  enforced by `tests/test_structure.py::test_all_hooks_stdlib_only`
- **Known secret formats are blocked from being committed** — the CI step
  *Check no secrets in tracked files* fails the build on a hit. Scope stated
  honestly rather than rounded up to "no secrets": it matches three key
  formats (`sk-…`, `AKIA…`, `ghp_…`) across `.py`/`.md`/`.json`/`.sh`, and
  skips test files. A credential in another format, or in a file type outside
  that list, is not caught by this gate.

**Intended, but NOT mechanically verified — scoped deliberately:**

- **PII redaction** — `redact.py` strips national IDs, phone numbers and email
  from the paths it covers. This is *not* a guarantee that no PII ever reaches a
  log: no end-to-end absence-of-leak test exists, and this repo's own
  `null_results/20260716-regex-composition-response-guard` records that regex
  cannot classify context reliably. Treat it as best-effort masking on known
  paths, not a boundary.
- **Parameterized queries** — required by `rules/security.md` for code written
  under this config. It is guidance to the model, not a check on shipped code;
  nothing in CI rejects string-concatenated SQL.

**Permission model — read this before assuming a posture it does not have:**

- `hooks/settings.json` is **broad-allow with explicit deny rules**, not
  deny-by-default. All 11 `permissions.allow` entries are wildcards, including
  `Bash(*)`, `Write(*)` and `Edit(*)`; the deny list then removes known
  destructive and high-risk operations.
- This is a deliberate choice for a single-developer workflow (2026-09-02: a
  narrower policy produced a permission-prompt storm and was reverted), not an
  oversight. It is documented here because an earlier version of this file
  called it *Deny-by-default*, which states the opposite of what the file does.
- The count of deny rules is deliberately NOT quoted here. It was stated as 17
  while the real number was 35, and replacing one hand-maintained number with
  another only schedules the next correction. Read `hooks/settings.json`, or
  gate the number if it ever needs to appear in prose.
