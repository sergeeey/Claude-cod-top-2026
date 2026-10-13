"""Tests for scripts/bench_hooks.py (hook latency benchmark and flag-equivalence check)."""

import json
import sys

import bench_hooks as bh
import pytest


class TestPureHelpers:
    @pytest.mark.parametrize(
        ("matcher", "expected"),
        [
            ("", "Bash"),
            ("*", "Bash"),
            ("Bash|Read|Grep|Glob", "Bash"),
            ("Edit|Write", "Edit"),
            ("mcp__*", "mcp__bench_tool"),
            ("Skill|Agent", "Skill"),
        ],
    )
    def test_pick_tool(self, matcher, expected):
        assert bh.pick_tool(matcher) == expected

    def test_resolve_command_string_and_list_python(self, tmp_path):
        cmd = "__PYTHON_CMD__ __CLAUDE_HOME__/hooks/x.py --flag"
        assert bh.resolve_command(cmd, "py", tmp_path)[0] == "py"
        argv = bh.resolve_command(cmd, ["py", "-S"], tmp_path)
        assert argv[:2] == ["py", "-S"]
        assert argv[-1] == "--flag"
        assert argv[2].endswith("/hooks/x.py")

    def test_non_python_command_is_not_rewritten(self, tmp_path):
        assert bh.resolve_command("powershell -Command beep", "py", tmp_path) == [
            "powershell",
            "-Command",
            "beep",
        ]

    def test_script_name(self):
        assert bh.script_name(["py", "C:/x/hooks/mentor_nudge.py"]) == "mentor_nudge.py"

    def test_collect_commands_keeps_order_and_defaults_matcher(self):
        settings = {
            "hooks": {
                "A": [{"hooks": [{"type": "command", "command": "c1"}]}],
                "B": [
                    {"matcher": "Bash", "hooks": [{"command": "c2"}, {"command": "c3"}]},
                    {"matcher": "", "hooks": [{"type": "prompt", "command": "ignored"}]},
                ],
            }
        }
        rows = bh.collect_commands(settings)
        assert [(r["event"], r["matcher"], r["command"]) for r in rows] == [
            ("A", "*", "c1"),
            ("B", "Bash", "c2"),
            ("B", "Bash", "c3"),
        ]

    def test_stats(self):
        s = bh.stats([10.0, 20.0, 30.0, 40.0, 50.0])
        assert s["median_ms"] == 30.0
        assert s["min_ms"] == 10.0
        assert s["n"] == 5

    def test_normalise_strips_volatile_but_keeps_content(self):
        a = bh._normalise("run at 2026-10-13T10:00:00+00:00 in bench_verify_ab12 pid 123456789")
        b = bh._normalise("run at 2027-01-01T00:00:00+00:00 in bench_verify_zz99 pid 987654321")
        assert a == b
        assert bh._normalise("result: allow") != bh._normalise("result: deny")

    def test_per_turn_totals_uses_max_within_phase_and_sum_across(self):
        def g(event, matcher, hooks, seq, par):
            return {
                "event": event,
                "matcher": matcher,
                "hooks": hooks,
                "sequential_sum_median_ms": seq,
                "group_parallel": {"median_ms": par},
            }

        report = {
            "groups": [
                g("UserPromptSubmit", "*", 13, 1000.0, 150.0),
                g("PreToolUse", "Bash", 4, 400.0, 100.0),
                g("PreToolUse", "*", 1, 90.0, 90.0),
                g("PostToolUse", "Bash", 9, 900.0, 130.0),
            ]
        }
        t = bh.per_turn_totals(report)
        assert t["user_message"]["processes"] == 13
        assert t["bash_call"]["processes"] == 14
        assert t["bash_call"]["sequential_sum_ms"] == 1390.0
        # Pre phase: max(100, 90) = 100; Post phase: 130
        assert t["bash_call"]["parallel_wall_ms"] == 230.0


@pytest.fixture
def fake_manifest(tmp_path):
    """A tiny hooks tree: one deterministic hook that reports __debug__, one random."""
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "debug_probe.py").write_text(
        "import sys\nsys.stdin.read()\nprint('debug', __debug__)\n", encoding="utf-8"
    )
    (hooks / "random_probe.py").write_text(
        "import random, sys\nsys.stdin.read()\n"
        "print('r', ''.join(random.choices('abcdefghij', k=12)))\n",
        encoding="utf-8",
    )
    manifest = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "__PYTHON_CMD__ __CLAUDE_HOME__/hooks/debug_probe.py",
                        },
                        {
                            "type": "command",
                            "command": "__PYTHON_CMD__ __CLAUDE_HOME__/hooks/random_probe.py",
                        },
                    ]
                }
            ]
        }
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, tmp_path


class TestVerifyFlags:
    """The verifier must catch a behaviour-changing flag and stay quiet for a harmless one."""

    def _run(self, fake_manifest, flag, capsys):
        path, home = fake_manifest
        rc = bh.main(
            [
                "--settings",
                str(path),
                "--claude-home",
                str(home),
                "--python",
                sys.executable,
                f"--verify-flags={flag}",
            ]
        )
        return rc, capsys.readouterr().out

    def test_detects_behaviour_changing_flag(self, fake_manifest, capsys):
        rc, out = self._run(fake_manifest, "-O", capsys)  # -O makes __debug__ False
        assert rc == 1
        assert "mismatches caused by the flag: 1" in out

    def test_harmless_flag_passes(self, fake_manifest, capsys):
        rc, out = self._run(fake_manifest, "-B", capsys)
        assert rc == 0
        assert "mismatches caused by the flag: 0" in out

    def test_nondeterministic_hook_is_excluded_not_blamed_on_the_flag(self, fake_manifest, capsys):
        _, out = self._run(fake_manifest, "-B", capsys)
        assert "random_probe.py" in out.split("excluded")[1].splitlines()[0]


class TestRunBenchmarkSmoke:
    def test_two_interleaved_variants_produce_two_reports(self, fake_manifest):
        path, home = fake_manifest
        args = bh.argparse.Namespace(
            settings=str(path),
            claude_home=str(home),
            python=sys.executable,
            python_flags="",
            runs=2,
            warmup=0,
            timeout=30.0,
            events=None,
            include_risky=False,
        )
        reports = bh.run_benchmark(
            args, {"plain": [sys.executable], "flags": [sys.executable, "-B"]}
        )
        assert set(reports) == {"plain", "flags"}
        for rep in reports.values():
            assert {h["hook"] for h in rep["hooks"]} == {"debug_probe.py", "random_probe.py"}
            assert rep["groups"][0]["hooks"] == 2
            assert all(h["n"] == 2 for h in rep["hooks"])
        assert reports["flags"]["environment"]["python_flags"] == "-B"
        assert reports["plain"]["environment"]["interleaved_variants"] == ["plain", "flags"]


class TestCliGuards:
    def test_ab_cannot_be_combined_with_python_flags(self, capsys):
        with pytest.raises(SystemExit) as exc:
            bh.main(["--ab=-S", "--python-flags=-B"])
        assert exc.value.code == 2
        assert "cannot be combined" in capsys.readouterr().err

    def test_verify_flags_cannot_be_combined_with_python_flags(self, capsys):
        with pytest.raises(SystemExit) as exc:
            bh.main(["--verify-flags=-S", "--python-flags=-B"])
        assert exc.value.code == 2

    def test_ab_and_verify_are_separate_modes(self, capsys):
        with pytest.raises(SystemExit) as exc:
            bh.main(["--ab=-S", "--verify-flags=-S"])
        assert exc.value.code == 2
