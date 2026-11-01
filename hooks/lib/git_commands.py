"""Real command invocations inside a shell command string -- not text that mentions them.

WHY (2026-11-01, found live in one session): three hooks decided "this is a git
commit / merge / force push" with a plain substring test on the command text
(`"git push --force" in cmd`, `"git merge" in cmd`, `"git commit" in cmd`).
That fires on text that is only *about* git: a `grep "git push --force"`, a
heredoc that writes a memory note, `git merge-base` (it contains "git merge"),
and -- the case that cost a lock-out -- `git push --force-with-lease=<ref>:<sha>`,
the protected form of a force push, which contained the substring of the
unprotected one. The result was a permission DENY on an owner-authorised push
and a "risky operation" nag on read-only commands.

This module replaces the substring test with the statement splitter and
tokenizer that `lib.security` already ships (quote-aware chain split, heredoc
bodies discarded, quote fragments rebuilt exactly as bash would). A command is
a git invocation only when `git` is the program of a statement, possibly behind
env assignments or a transparent wrapper (`env`, `sudo`, `nohup`, ...), or
inside the payload of an interpreter (`bash -c "..."`, `ssh host "..."`).

Deliberately NOT a general shell parser: anything it cannot read it reports
through `runs_unparsed_shell()` so a caller can fall back to the old, stricter
substring scan instead of silently allowing it.
"""

from __future__ import annotations

import re

from lib.security import shell_statement_tokens, split_shell_statements

# Programs that run another program given as the following arguments.
_WRAPPERS = frozenset(
    {"env", "command", "nohup", "time", "exec", "sudo", "nice", "xargs", "builtin", "timeout"}
)
# Programs that interpret a string (or stdin) as shell code.
_INTERPRETERS = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "dash",
        "ksh",
        "fish",
        "cmd",
        "cmd.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
    }
)
# Programs that carry a command string to somewhere else.
_REMOTE_RUNNERS = frozenset({"ssh", "su", "watch", "eval"})
# Flags after which an interpreter reads its code from the next argument.
_INLINE_CODE_FLAGS = frozenset({"-c", "/c", "-command", "-lc", "-ic", "-encodedcommand", "-e"})

# Programs a caller asks about; only these are looked for behind a wrapper.
_WRAPPED_OF_INTEREST = frozenset({"git", "git.exe", "rm", "rm.exe"})

_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# git global options that consume the following token as their value.
_GIT_OPTS_WITH_VALUE = frozenset(
    {"-c", "-C", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
)
# `<ref>:<sha>` -- a lease that names the value it expects.
_EXPLICIT_LEASE_RE = re.compile(r"^[^:\s]+:[0-9a-fA-F]{7,64}$")

_MAX_DEPTH = 3
_MAX_WRAPPER_SCAN = 12


def _basename(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _strip_prefix(tokens: list[str]) -> list[str]:
    """Drop leading `VAR=value` assignments."""
    i = 0
    while i < len(tokens) and _ASSIGN_RE.match(tokens[i]):
        i += 1
    return tokens[i:]


def invocations(command: str, _depth: int = 0) -> list[tuple[str, list[str]]]:
    """Return `(program, args)` for every real command in `command`.

    `program` is the lower-cased basename. Text inside quotes or heredoc bodies
    is never returned as a command; payloads of interpreters and remote runners
    are parsed recursively.
    """
    found: list[tuple[str, list[str]]] = []
    if _depth > _MAX_DEPTH or not command:
        return found
    for statement in split_shell_statements(command):
        tokens = _strip_prefix(shell_statement_tokens(statement))
        if not tokens:
            continue
        program = _basename(tokens[0])
        args = tokens[1:]
        if program in _WRAPPERS:
            # `sudo -u root git push` / `env -i X=1 rm -rf x`: find the wrapped program.
            for k, tok in enumerate(args[:_MAX_WRAPPER_SCAN]):
                if _basename(tok) in _WRAPPED_OF_INTEREST:
                    program, args = _basename(tok).removesuffix(".exe"), args[k + 1 :]
                    break
            else:
                found.append((program, args))
                continue
        if program in ("git", "git.exe"):
            found.append(("git", args))
        elif program in _INTERPRETERS or program in _REMOTE_RUNNERS:
            found.append((program, args))
            for tok in args:
                if " " in tok.strip():
                    found.extend(invocations(tok, _depth + 1))
        else:
            found.append((program, args))
    return found


def _git_subcommand(args: list[str]) -> tuple[str, list[str]] | None:
    """Split `git`'s arguments into `(subcommand, rest)`, skipping global options."""
    j = 0
    while j < len(args):
        token = args[j]
        if token in _GIT_OPTS_WITH_VALUE:
            j += 2
        elif token.startswith("-"):
            j += 1
        else:
            return args[j], args[j + 1 :]
    return None


def git_invocations(command: str) -> list[tuple[str, list[str]]]:
    """Return `(subcommand, args)` for every real `git <subcommand> ...` call."""
    out: list[tuple[str, list[str]]] = []
    for program, args in invocations(command):
        if program == "git":
            parsed = _git_subcommand(args)
            if parsed:
                out.append(parsed)
    return out


def runs_unparsed_shell(command: str) -> bool:
    """True when a statement feeds code to an interpreter this module cannot read.

    Example: `echo "git push --force" | bash` -- `bash` has no inline-code flag,
    so it executes whatever arrives on stdin. Callers use this to keep their
    older, stricter text scan for exactly that shape.
    """
    for program, args in invocations(command):
        if program in _INTERPRETERS and not any(a.lower() in _INLINE_CODE_FLAGS for a in args):
            return True
    return False


# Programs that only print, search, copy or move text. A command made solely of
# these (plus harmless git subcommands) cannot execute text it merely contains.
_INERT_PROGRAMS = frozenset(
    {
        "cd", "pushd", "popd", "pwd", "echo", "printf", "cat", "tee", "grep", "egrep", "fgrep",
        "rg", "ag", "sed", "awk", "head", "tail", "wc", "ls", "dir", "type", "sort", "uniq",
        "cut", "tr", "diff", "mkdir", "touch", "cp", "mv", "true", "false", "date", "sleep",
        "export", "set", "test", "[",
    }
)  # fmt: skip
_INERT_GIT_SUBCOMMANDS = frozenset(
    {
        "commit", "log", "show", "diff", "status", "add", "tag", "notes", "stash", "grep",
        "blame", "branch", "config", "describe", "rev-parse", "rev-list", "ls-files",
        "merge-base", "remote", "fetch", "cat-file", "shortlog", "reflog",
    }
)  # fmt: skip
_COMMAND_SUBSTITUTION_MARKERS = ("$(", "`", "<(", ">(")


def is_inert_text_command(command: str) -> bool:
    """True when `command` only moves or prints text and cannot execute what it contains.

    Used to exempt text that merely mentions a dangerous command (a grep pattern,
    a commit message, a heredoc note) from a legacy substring rule. Anything with
    command substitution, a subshell/group (`( ... )`, `{ ...; }`), an interpreter,
    a wrapper, or a git subcommand outside the harmless list is NOT inert, so the
    stricter rule keeps applying to it.
    """
    if any(marker in command for marker in _COMMAND_SUBSTITUTION_MARKERS):
        return False
    seen_any = False
    for program, args in invocations(command):
        seen_any = True
        if program in _INERT_PROGRAMS:
            continue
        if program == "git":
            parsed = _git_subcommand(args)
            if parsed and parsed[0] in _INERT_GIT_SUBCOMMANDS:
                continue
        return False
    return seen_any


def neutralize_explicit_leases(text: str) -> str:
    """Rewrite `--force-with-lease=<ref>:<sha>` so a text scan for `--force` ignores it."""
    return _EXPLICIT_LEASE_TOKEN_RE.sub("--explicit-lease", text)


_EXPLICIT_LEASE_TOKEN_RE = re.compile(r"--force-with-lease=[^\s:=]+:[0-9a-fA-F]{7,64}(?=\s|$)")


def force_push_reason(args: list[str], *, allow_explicit_lease: bool = False) -> str | None:
    """Why a `git push` argument list can overwrite remote history, or None.

    `allow_explicit_lease=True` accepts `--force-with-lease=<ref>:<sha>`: the push
    succeeds only if the remote still holds exactly <sha>, so it cannot clobber
    work it has not seen. A bare `--force-with-lease` is NOT accepted -- without
    a named value git trusts the local remote-tracking ref, which a fetch moves.
    """
    for arg in args:
        if arg == "--force" or arg.startswith("--force="):
            return "bare --force"
        if arg == "--force-with-lease":
            return "--force-with-lease without an explicit <ref>:<sha>"
        if arg.startswith("--force-with-lease="):
            value = arg.split("=", 1)[1]
            if not _EXPLICIT_LEASE_RE.match(value):
                return "--force-with-lease without an explicit <ref>:<sha>"
            if not allow_explicit_lease:
                return "--force-with-lease=<ref>:<sha>"
            continue
        if arg.startswith("--"):
            continue
        if arg.startswith("-") and "f" in arg[1:]:
            return "-f"
        if arg.startswith("+") or ":+" in arg:
            return "forced refspec (+)"
    return None


def force_push_in(command: str, *, allow_explicit_lease: bool = False) -> str | None:
    """Reason of the first force-style `git push` in `command`, or None."""
    for sub, args in git_invocations(command):
        if sub == "push":
            reason = force_push_reason(args, allow_explicit_lease=allow_explicit_lease)
            if reason:
                return reason
    return None


def has_git_subcommand(command: str, *subcommands: str) -> bool:
    """True if `command` really runs one of the given `git <subcommand>`s."""
    wanted = set(subcommands)
    return any(sub in wanted for sub, _ in git_invocations(command))
