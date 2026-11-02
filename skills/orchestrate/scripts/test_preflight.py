#!/usr/bin/env python3
"""preflight.py's contract: one verdict line per exit code, and no silent "clear".

    python3 skills/orchestrate/scripts/test_preflight.py

A fake `pixi` stands in for the architecture CLI, so these run with no opengwasdb-stores
checkout, no network and no Herdr.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("preflight.py")


def executable(path: Path, body: str) -> Path:
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def stores(root: Path) -> Path:
    """A checkout that looks like one with the architecture CLI."""
    (root / "src/project_site").mkdir(parents=True)
    (root / "pixi.toml").write_text("[workspace]\n")
    (root / "src/project_site/architecture.py").write_text("")
    return root


def pixi(tmp: Path, code: int, output: str) -> Path:
    calls = tmp / "pixi-args.txt"
    fake = executable(tmp / "pixi-bin" / "pixi", (
        f'printf "%s\\n" "$@" | tr "\\n" " " > {calls}\n'
        f"printf '%s\\n' '✨ Pixi task (architecture in dev): python3 -m project_site.architecture'\n"
        f"cat <<'OUT'\n{output}\nOUT\n"
        f"exit {code}\n"
    ))
    fake.parent.mkdir(parents=True, exist_ok=True)
    return fake


class Preflight(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.stores = stores(self.tmp / "stores")
        # The fake `pixi` shadows the real one; everything else stays on PATH.
        self.path = f"{self.tmp}/pixi-bin:{os.environ['PATH']}"
        (self.tmp / "pixi-bin").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_preflight(self, *extra: str, path: str | None = None) -> subprocess.CompletedProcess:
        environment = {**os.environ, "PATH": path if path is not None else self.path}
        environment.pop("ORCH_STORES", None)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--ticket", "opengwas/opengwasdb#338",
             "--files", "opengwasdb/store/convert.py", "opengwasdb/query/facade.py", *extra],
            capture_output=True, text=True, env=environment, timeout=120,
        )

    def verdict(self, result: subprocess.CompletedProcess) -> str:
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return lines[-1] if lines else ""

    def test_launch_on_exit_0(self) -> None:
        pixi(self.tmp, 0, "2 files on 2 components for opengwasdb#338\nmeets no other work")
        result = self.run_preflight("--stores", str(self.stores))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # The owner prefix is cut to the map's form.
        self.assertTrue(self.verdict(result).startswith("LAUNCH opengwasdb#338:"), self.verdict(result))
        self.assertIn("2 components", self.verdict(result))

    def test_stop_on_uncoordinated_meet(self) -> None:
        pixi(self.tmp, 1, "\n".join([
            "2 files on 1 component for opengwasdb#338",
            "Repair and re-encode (maintenance) meets 1 other owner:",
            "  opengwasdb-stores#232 publish the Store Releases",
            "    opengwasdb-stores#344 [active, cited] opengwasdb/store/convert.py",
            "    UNCOORDINATED: no blocking edge links opengwasdb#338 and opengwasdb-stores#344",
        ]))
        result = self.run_preflight("--stores", str(self.stores))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        verdict = self.verdict(result)
        self.assertTrue(verdict.startswith("STOP opengwasdb#338:"), verdict)
        self.assertIn("opengwasdb-stores#344", verdict)

    def test_stop_on_unlinkable_meet(self) -> None:
        pixi(self.tmp, 1, "\n".join([
            "2 files on 1 component for opengwasdb#338",
            "    UNLINKABLE: opengwasdb:orch/1-big belongs to an epic as a whole",
        ]))
        result = self.run_preflight("--stores", str(self.stores))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(self.verdict(result).startswith("STOP "), self.verdict(result))

    def test_unchecked_on_exit_2(self) -> None:
        pixi(self.tmp, 2, "cannot decide: engine-side work was not measured: no model at main")
        result = self.run_preflight("--stores", str(self.stores))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        verdict = self.verdict(result)
        self.assertTrue(verdict.startswith("UNCHECKED opengwasdb#338:"), verdict)
        self.assertIn("engine-side work was not measured", verdict)

    def test_unchecked_when_the_cli_is_missing(self) -> None:
        # No pixi on PATH at all.
        result = self.run_preflight("--stores", str(self.stores), path=str(self.tmp / "empty"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("UNCHECKED", self.verdict(result))
        self.assertIn("pixi", self.verdict(result))

    def test_unchecked_when_the_checkout_is_old_or_absent(self) -> None:
        pixi(self.tmp, 0, "meets no other work")
        result = self.run_preflight("--stores", str(self.tmp / "nothing-here"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("UNCHECKED", self.verdict(result))
        self.assertIn("nothing-here", self.verdict(result))

    def test_unchecked_when_the_cli_fails_without_a_verdict(self) -> None:
        # A broken environment exits 1, like a meet does. Never read that as STOP.
        pixi(self.tmp, 1, "ModuleNotFoundError: No module named 'project_site'")
        result = self.run_preflight("--stores", str(self.stores))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("UNCHECKED", self.verdict(result))

    def test_verdict_names_each_owner_once(self) -> None:
        # The CLI prints a meet again on every component it touches, and an epic's
        # integration branch is unlinkable rather than uncoordinated. The verdict is one line.
        block = [
            "    opengwasdb-stores#344 [active, cited] opengwasdb/store/convert.py",
            "    UNCOORDINATED: no blocking edge links opengwasdb#338 and opengwasdb-stores#344",
            "    UNLINKABLE: opengwasdb:orch/58-deepen-modules belongs to an epic as a whole",
        ]
        pixi(self.tmp, 1, "\n".join([
            "2 files on 2 components for opengwasdb#338",
            "Store contract model (model) meets 1 other owner:", *block,
            "Query (query) meets 1 other owner:", *block,
        ]))
        result = self.run_preflight("--stores", str(self.stores))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        verdict = self.verdict(result)
        self.assertEqual(verdict.count("opengwasdb-stores#344"), 1, verdict)
        self.assertIn("integration branch", verdict)
        self.assertLess(len(verdict), 300, verdict)

    def test_forwards_the_check_to_the_cli(self) -> None:
        pixi(self.tmp, 0, "meets no other work")
        self.run_preflight("--stores", str(self.stores), "--local", "/nonexistent/engine")
        calls = (self.tmp / "pixi-args.txt").read_text()
        self.assertIn("run -e dev architecture conflicts", calls)
        self.assertIn("--ticket opengwasdb#338", calls)
        self.assertIn("--files opengwasdb/store/convert.py opengwasdb/query/facade.py", calls)
        self.assertIn("--local /nonexistent/engine", calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
