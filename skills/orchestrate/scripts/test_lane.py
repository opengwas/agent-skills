#!/usr/bin/env python3
"""lane.py's agent names: valid for Herdr, unique per run and ticket, stable within a run.

    python3 skills/orchestrate/scripts/test_lane.py
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lane  # noqa: E402

HERDR_NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}")


class AgentName(unittest.TestCase):
    def test_a_finished_runs_agent_does_not_block_this_runs_ticket(self) -> None:
        self.assertNotEqual(lane.agent_name(Path("/runs/one"), "7"), lane.agent_name(Path("/runs/two"), "7"))

    def test_stable_within_a_run_and_distinct_per_ticket(self) -> None:
        run = Path("/runs/one")
        self.assertEqual(lane.agent_name(run, "7"), lane.agent_name(run, "7"))
        self.assertNotEqual(lane.agent_name(run, "7"), lane.agent_name(run, "8"))

    def test_always_a_valid_herdr_name(self) -> None:
        for ticket in ("7", "t1", "opengwas/og-dev-hub#9", "X" * 80, "###", "Ünï"):
            name = lane.agent_name(Path("/runs/one"), ticket)
            self.assertRegex(name, HERDR_NAME)
            self.assertTrue(HERDR_NAME.fullmatch(name), name)

    def test_long_tickets_keep_the_run_suffix(self) -> None:
        self.assertEqual(lane.agent_name(Path("/runs/one"), "a" * 80)[-7:],
                         lane.agent_name(Path("/runs/one"), "b" * 5)[-7:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
