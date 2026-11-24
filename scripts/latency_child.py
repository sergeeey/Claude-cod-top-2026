"""Run one hook the way `python hook.py` does, and write its CPU time and exit code.

Used by scripts/latency_stand.py. The hook source is compiled and run in this process as
__main__, with its own directory first on sys.path, which is what the harness does. The child
imports nothing beyond the hook's own needs, so the stand does not add modules to the hook's
startup (an earlier version used runpy and ctypes and added about 15 ms per process). CPU time
comes from os.times() (user plus system) and goes to --stats as "<cpu_ms> <exit>". Peak memory
is sampled by the parent, not here.
"""

import builtins
import os
import sys


def main() -> None:
    hook = sys.argv[sys.argv.index("--hook") + 1]
    stats_path = sys.argv[sys.argv.index("--stats") + 1]
    sys.path.insert(0, os.path.dirname(os.path.abspath(hook)))
    sys.argv = [hook]
    code = 0
    try:
        with open(hook, "rb") as fh:
            source = fh.read()
        namespace = {"__name__": "__main__", "__file__": hook, "__builtins__": builtins}
        exec(compile(source, hook, "exec"), namespace)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except BaseException:
        code = 1
        raise
    finally:
        times = os.times()
        with open(stats_path, "w", encoding="ascii") as fh:
            fh.write(f"{(times.user + times.system) * 1000:.3f} {code}")
    sys.exit(code)


if __name__ == "__main__":
    main()
