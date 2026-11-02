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


def pixi(tmp: Path, code: int, output: str, sleep: int = 0) -> Path:
    """A fake `pixi` that prints `output`, sleeps, and exits `code`."""
    calls = tmp / "pixi-args.txt"
    fake = executable(tmp / "pixi-bin" / "pixi", (
        f'printf "%s\\n" "$@" | tr "\\n" " " > {calls}\n'
        f"printf '%s\\n' '✨ Pixi task (architecture in dev): python3 -m project_site.architecture'\n"
        f"cat <<'OUT'\n{output}\nOUT\n"
        f"sleep {sleep}\n"
        f"exit {code}\n"
    ))
    fake.parent.mkdir(parents=True, exist_ok=True)
    return fake


def pixi_bytes(tmp: Path, code: int, printf_body: str) -> Path:
    """A fake `pixi` that writes raw bytes, so output that is not UTF-8 can be tested."""
    fake = executable(tmp / "pixi-bin" / "pixi", (
        "printf '%s\\n' '✨ Pixi task (architecture in dev): python3 -m project_site.architecture'\n"
        f"printf '{printf_body}'\n"
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

    def run_preflight(self, *extra: str, path: str | None = None,
                      home: Path | None = None) -> subprocess.CompletedProcess:
        environment = {**os.environ, "PATH": path if path is not None else self.path}
        environment.pop("ORCH_STORES", None)
        if home is not None:
            environment["HOME"] = str(home)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--ticket", "opengwas/opengwasdb#338",
             "--files", "opengwasdb/store/convert.py", "opengwasdb/query/facade.py", *extra],
            capture_output=True, text=True, env=environment, timeout=120,
        )

    def verdict(self, result: subprocess.CompletedProcess) -> str:
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return lines[-1] if lines else ""

    def assertVerdict(self, result: subprocess.CompletedProcess, word: str, status: int) -> str:
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        verdict = self.verdict(result)
        self.assertTrue(verdict.startswith(f"{word} opengwasdb#338:"), verdict)
        return verdict

    # --- exit 0: launch, but only on a recognisable success -------------------

    def test_launch_on_exit_0(self) -> None:
        pixi(self.tmp, 0, "2 files on 2 components for opengwasdb#338\nmeets no other work")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "LAUNCH", 0)
        self.assertIn("2 components", verdict)  # the owner prefix is cut to the map's form

    def test_launch_on_a_coordinated_meet(self) -> None:
        pixi(self.tmp, 0, "\n".join([
            "2 files on 1 component for opengwasdb#338",
            "Reference Completion (completion) meets 1 other owner:",
            "  opengwasdb#58 Shallow-module cleanup ledger",
            "    opengwasdb#357 [building, branch] opengwasdb:orch/58/357",
            "    coordinated: opengwasdb#338 waits for opengwasdb#357",
        ]))
        self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "LAUNCH", 0)

    def test_unchecked_on_empty_output_with_exit_0(self) -> None:
        pixi(self.tmp, 0, "")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "UNCHECKED", 2)
        self.assertIn("did not say", verdict)

    def test_unchecked_on_garbled_output_with_exit_0(self) -> None:
        pixi(self.tmp, 0, "garbled output")
        self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "UNCHECKED", 2)

    def test_unchecked_on_a_contradiction_with_exit_0(self) -> None:
        # Success status with a "cannot decide" line: the map contradicts itself.
        pixi(self.tmp, 0, "meets no other work\ncannot decide: broken collection")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "UNCHECKED", 2)
        self.assertIn("broken collection", verdict)

    # --- exit 1: always stop --------------------------------------------------

    def test_stop_on_uncoordinated_meet(self) -> None:
        pixi(self.tmp, 1, "\n".join([
            "2 files on 1 component for opengwasdb#338",
            "Repair and re-encode (maintenance) meets 1 other owner:",
            "  opengwasdb-stores#232 publish the Store Releases",
            "    opengwasdb-stores#344 [active, cited] opengwasdb/store/convert.py",
            "    UNCOORDINATED: no blocking edge links opengwasdb#338 and opengwasdb-stores#344",
        ]))
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "STOP", 1)
        self.assertIn("opengwasdb-stores#344", verdict)

    def test_stop_when_exit_1_cannot_be_parsed(self) -> None:
        # Exit 1 is a conflict whatever the body says; show the body and ask.
        pixi(self.tmp, 1, "ModuleNotFoundError: No module named 'project_site'")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "STOP", 1)
        self.assertIn("couldn't describe", verdict)
        self.assertIn("show its output", verdict)

    def test_stop_names_the_branch_of_an_unlinkable_meet(self) -> None:
        pixi(self.tmp, 1, "\n".join([
            "2 files on 1 component for opengwasdb#338",
            "Reference Completion (completion) meets 1 other owner:",
            "  opengwasdb#58 Shallow-module cleanup ledger (delete first, then deepen)",
            "    branch:opengwasdb:orch/58-deepen-modules [building, branch]",
            "    UNLINKABLE: opengwasdb:orch/58-deepen-modules belongs to an epic as a whole, "
            "so no blocking edge can link it to a single ticket; asking a person is the safe default",
        ]))
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "STOP", 1)
        self.assertIn("orch/58-deepen-modules", verdict)
        self.assertIn("opengwasdb#58", verdict)

    # --- everything else: one UNCHECKED verdict -------------------------------

    def test_unchecked_on_exit_2(self) -> None:
        pixi(self.tmp, 2, "cannot decide: engine-side work was not measured: no model at main")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "UNCHECKED", 2)
        self.assertIn("engine-side work was not measured", verdict)

    def test_unchecked_on_an_unexpected_exit_code(self) -> None:
        pixi(self.tmp, 17, "something else entirely")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "UNCHECKED", 2)
        self.assertIn("17", verdict)

    def test_unchecked_on_a_timeout(self) -> None:
        pixi(self.tmp, 0, "meets no other work", sleep=5)
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores), "--timeout", "1"),
                                     "UNCHECKED", 2)
        self.assertIn("did not answer", verdict)

    def test_unchecked_on_invalid_utf8(self) -> None:
        pixi_bytes(self.tmp, 2, "cannot decide: \\xff\\xfe broken")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "UNCHECKED", 2)
        self.assertIn("broken", verdict)

    def test_unchecked_when_the_cli_is_missing(self) -> None:
        # No pixi on PATH at all.
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores),
                                                       path=str(self.tmp / "empty")), "UNCHECKED", 2)
        self.assertIn("pixi", verdict)

    def test_unchecked_when_the_checkout_is_old_or_absent(self) -> None:
        pixi(self.tmp, 0, "meets no other work")
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.tmp / "nothing-here")),
                                     "UNCHECKED", 2)
        self.assertIn("nothing-here", verdict)

    # --- the one-line contract ------------------------------------------------

    def test_verdict_names_each_owner_once(self) -> None:
        # The CLI prints a meet again on every component it touches. The verdict is one line.
        block = [
            "    opengwasdb-stores#344 [active, cited] opengwasdb/store/convert.py",
            "    UNCOORDINATED: no blocking edge links opengwasdb#338 and opengwasdb-stores#344",
            "    UNLINKABLE: opengwasdb:orch/58-deepen-modules belongs to an epic as a whole",
        ]
        pixi(self.tmp, 1, "\n".join([
            "2 files on 2 components for opengwasdb#338",
            "  opengwasdb#58 Shallow-module cleanup ledger",
            "Store contract model (model) meets 2 other owners:", *block,
            "Query (query) meets 2 other owners:", *block,
        ]))
        verdict = self.assertVerdict(self.run_preflight("--stores", str(self.stores)), "STOP", 1)
        self.assertEqual(verdict.count("opengwasdb-stores#344"), 1, verdict)
        self.assertEqual(verdict.count("orch/58-deepen-modules"), 1, verdict)
        self.assertLess(len(verdict), 300, verdict)

    def test_forwards_the_check_to_the_cli(self) -> None:
        pixi(self.tmp, 0, "meets no other work")
        self.run_preflight("--stores", str(self.stores), "--local", "/nonexistent/engine")
        calls = (self.tmp / "pixi-args.txt").read_text()
        self.assertIn("run -e dev architecture conflicts", calls)
        self.assertIn("--ticket opengwasdb#338", calls)
        self.assertIn("--files opengwasdb/store/convert.py opengwasdb/query/facade.py", calls)
        self.assertIn("--local /nonexistent/engine", calls)

    def test_counts_the_host_clones_that_are_there(self) -> None:
        pixi(self.tmp, 0, "meets no other work")
        home = self.tmp / "home"
        for clone in ("opengwasdb", "opengwasdb-stores"):
            (home / "repo" / clone / ".git").mkdir(parents=True)
        self.assertVerdict(self.run_preflight("--stores", str(self.stores), home=home), "LAUNCH", 0)
        calls = (self.tmp / "pixi-args.txt").read_text()
        self.assertIn(f"--local {home}/repo/opengwasdb {home}/repo/opengwasdb-stores", calls)

    def test_omits_local_when_the_host_has_no_clone(self) -> None:
        # The CLI refuses an empty `--local`, so sending one turns a valid check into UNCHECKED.
        pixi(self.tmp, 0, "meets no other work")
        home = self.tmp / "home"
        home.mkdir()
        self.assertVerdict(self.run_preflight("--stores", str(self.stores), home=home), "LAUNCH", 0)
        self.assertNotIn("--local", (self.tmp / "pixi-args.txt").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
