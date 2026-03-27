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

This project follows these security principles by design:

- **No external dependencies** in hooks (stdlib-only Python)
- **PII never in logs** — redaction hook strips national IDs, phone, email
- **Parameterized queries only** — SQL injection prevention in rules
- **Secrets in env vars only** — never hardcoded, never committed
- **Deny-by-default** — 17 deny patterns in settings.json
