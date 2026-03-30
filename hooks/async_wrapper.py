#!/usr/bin/env python3
"""Universal async launcher for Claude Code hooks.

WHY: Claude Code waits for hook exit before proceeding. Slow hooks (pattern
analysis, memory writes, external API calls) create perceptible latency in the
main interaction loop. This wrapper forks the actual hook as a detached
subprocess and exits immediately (exit 0), so Claude Code is never blocked.

Usage:
    python async_wrapper.py python actual_hook.py [--any-flags]

The wrapper:
1. Reads all stdin data (hook payload from Claude Code).
2. Spawns the actual hook as a detached subprocess, piping stdin data to it.
3. Exits with code 0 immediately — pass-through for Claude Code.

Windows note: uses DETACHED_PROCESS (0x00000008) flag instead of os.fork(),
which is unavailable on Windows. The child runs in a detached console, fully
independent of the parent process lifetime.
"""

import subprocess
import sys


# WHY: Windows API constant for CreateProcess — tells the OS to detach the
# child from the parent's console. Without this flag on Windows, the child
# inherits the parent's console handle and may be killed when the parent exits.
_DETACHED_PROCESS: int = 0x00000008

# WHY: CREATE_NO_WINDOW prevents a flash of a console window for the child
# process on Windows. Combined with DETACHED_PROCESS it ensures a truly
# invisible background execution.
_CREATE_NO_WINDOW: int = 0x08000000


def _build_creation_flags() -> int:
    """Return subprocess creation flags appropriate for the current platform.

    WHY: os.fork() is Unix-only. On Windows we must use Popen creation flags
    to achieve detachment. On Unix we use 0 (no special flags) because the
    parent exits immediately anyway, making the child effectively orphaned and
    adopted by init/systemd.
    """
    if sys.platform == "win32":
        return _DETACHED_PROCESS | _CREATE_NO_WINDOW
    # WHY: on Unix, start_new_session=True (set in Popen call) is the idiomatic
    # way to detach; no extra creation flags needed.
    return 0


def _read_stdin_bytes() -> bytes:
    """Read all available stdin data as raw bytes.

    WHY: We must drain stdin BEFORE spawning the child, because stdin is a
    one-shot pipe — once the parent reads it, the child cannot re-read the
    same data from the OS pipe. We capture it here and pass it via `input=`
    to Popen, which creates a fresh pipe for the child.
    """
    try:
        return sys.stdin.buffer.read()
    except (OSError, ValueError):
        # WHY: ValueError is raised when stdin is already closed (e.g., when
        # the hook is invoked without a TTY in some CI environments).
        return b""


def main() -> None:
    """Spawn the actual hook as a detached subprocess and exit immediately."""
    # argv[0] is this script; argv[1:] is the actual command to run.
    if len(sys.argv) < 2:
        # WHY: exit 0 even on misconfiguration — the wrapper must never block
        # Claude Code with a non-zero exit that could be misinterpreted as a
        # hook decision (exit 2 = block, exit 1 = warning in some protocols).
        sys.exit(0)

    child_cmd: list[str] = sys.argv[1:]
    stdin_data: bytes = _read_stdin_bytes()
    creation_flags: int = _build_creation_flags()

    # WHY: start_new_session=True on Unix detaches the child from the parent's
    # process group, so it is not killed by SIGHUP when the parent exits.
    # On Windows this argument is silently ignored when creation_flags includes
    # DETACHED_PROCESS, so it is safe to pass on both platforms.
    popen_kwargs: dict = {
        "stdin": subprocess.PIPE,
        # WHY: redirect stdout/stderr to DEVNULL for the child — the output
        # is not visible to Claude Code anyway (parent already exited), and
        # leaving them open can cause ResourceWarning on some Python versions.
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "start_new_session": True,
        "creationflags": creation_flags,
    }

    # WHY: We do not pass `close_fds` explicitly on Windows — Python 3.7+
    # handles it correctly per platform. On Unix close_fds=True is the
    # default, which prevents leaked file descriptors in the child.

    try:
        proc = subprocess.Popen(child_cmd, **popen_kwargs)  # noqa: S603
        # WHY: communicate() writes stdin_data and closes the pipe cleanly.
        # We call it with timeout=0 (non-blocking write start) — we do NOT
        # wait for the child to finish. The Popen object is immediately
        # dereferenced after this call; the child continues independently.
        # timeout=None would block; we use proc.stdin.write + close instead
        # to avoid any waiting.
        if stdin_data and proc.stdin is not None:
            try:
                proc.stdin.write(stdin_data)
                proc.stdin.close()
            except (OSError, BrokenPipeError):
                # WHY: child may have already exited (e.g., syntax error in
                # hook script). This is not an error condition for the wrapper.
                pass
    except (OSError, FileNotFoundError):
        # WHY: if the child command is not found or not executable, we still
        # exit 0. The wrapper's contract with Claude Code is "never block",
        # not "guarantee child execution".
        pass

    # WHY: Explicit exit(0) rather than falling off main(). In hooks, a
    # missing explicit exit can sometimes result in non-zero exit codes from
    # Python's atexit handlers or garbage collection on Windows.
    sys.exit(0)


if __name__ == "__main__":
    main()
