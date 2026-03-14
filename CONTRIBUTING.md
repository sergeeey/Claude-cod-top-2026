# Contributing

Thank you for your interest in contributing to Claude Code Config!

### How to Contribute

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature`
3. **Make changes** following the guidelines below
4. **Test**: run `bash tests/test_all.sh` before submitting
5. **Commit**: use [Conventional Commits](https://www.conventionalcommits.org/) format
   - `feat:` — new feature
   - `fix:` — bug fix
   - `docs:` — documentation only
   - `refactor:` — code change that neither fixes nor adds
   - `test:` — adding or updating tests
6. **Open a Pull Request** against `main`

### Code Style

- **Shell scripts**: POSIX-compatible bash, `set -e`, quote all variables
- **Python hooks**: Python 3.8+, type hints, no external dependencies
- **Markdown**: ATX headings (`#`), fenced code blocks, max 100 chars/line
- **Line endings**: LF only (enforced by `.gitattributes`)

### What We Welcome

- New hooks (deterministic guards for Claude behavior)
- New skills (domain knowledge with CSO-optimized descriptions)
- Translations and localization
- Bug reports with reproduction steps
- Performance improvements (token economy)

### What We Don't Accept

- Changes that break backward compatibility without discussion
- Features that increase CLAUDE.md beyond 60 lines (token budget)
- Dependencies on external packages in hooks (must be stdlib-only)
- Removal of Evidence Policy markers or security guards

### Pull Request Checklist

- [ ] Tests pass (`bash tests/test_all.sh`)
- [ ] No secrets or PII in committed files
- [ ] CHANGELOG.md updated (if user-facing change)
- [ ] Skill descriptions follow CSO format ("USE when...", not summary)
