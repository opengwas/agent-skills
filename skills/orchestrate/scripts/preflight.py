#!/usr/bin/env python3
"""Does this ticket's lane meet uncoordinated live work? Ask the architecture map before launching it.

    preflight.py --ticket <repo#n> --files <path>... [--stores DIR] [--local GIT_DIR...]
                 [--repo engine|registry] [--timeout S] [-- <architecture conflicts flags>]

Run from anywhere. It runs `conflicts` from the architecture CLI (#419, epic #416) in an
opengwasdb-stores checkout — `--stores`, else `$ORCH_STORES`, else `~/repo/opengwasdb-stores` —
passing `--local` the host's own clones (`~/repo/opengwasdb`, `~/repo/opengwasdb-stores`) so
that lanes which exist only on this host count. The files are the ones the ticket's notes and
its brief assign it, spelled as the repository spells them. The ticket is the map's
(`opengwasdb#338`); an `owner/repo#n` label is accepted and cut to that form.

Prints the CLI's own output, then one verdict line and its action as the exit status:

  LAUNCH     0  meets no other live work, or only work a blocking edge coordinates. Launch.
  STOP       1  an uncoordinated or unlinkable meet, named. Stop and ask the user.
  UNCHECKED  2  it could not decide, or the checkout or CLI is missing. Say so once, then launch.

Never read UNCHECKED as LAUNCH: the map did not answer.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

DEFAULT_STORES = Path.home() / "repo/opengwasdb-stores"
DEFAULT_LOCAL = (Path.home() / "repo/opengwasdb", Path.home() / "repo/opengwasdb-stores")
MEET = re.compile(r"^\s+(UNCOORDINATED|UNLINKABLE): (.*)$", re.MULTILINE)
TICKET = re.compile(r"\b([A-Za-z0-9_.-]+#\d+)\b")
PLACED = re.compile(r"(\d+) files on (\d+) components")
REASON = re.compile(r"^cannot decide: (.*)$", re.MULTILINE)


def ticket_label(value: str) -> str:
    """The map spells a ticket `repo#n`; take an `owner/repo#n` label and cut it to that."""
    bare = value.rsplit("/", 1)[-1]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+#\d+", bare):
        raise argparse.ArgumentTypeError(f"{value!r} is not a ticket: give it as owner/repo#n")
    return bare


def stores_dir(given: str | None) -> Path:
    return Path(given or os.environ.get("ORCH_STORES") or DEFAULT_STORES).expanduser()


def local_dirs(given: Sequence[str]) -> list[str]:
    return list(given) if given else [str(p) for p in DEFAULT_LOCAL if (p / ".git").exists()]


def run(args: argparse.Namespace) -> tuple[int, str]:
    """`(exit status, the CLI's output)`: the CLI run in the checkout, or the reason it did not run."""
    directory = stores_dir(args.stores)
    missing = [p for p in ("pixi.toml", "src/project_site/architecture.py") if not (directory / p).exists()]
    if missing:
        return 2, f"no architecture CLI at {directory}: {', '.join(missing)} is not there"
    command = ["pixi", "run", "-e", "dev", "architecture", "conflicts",
               "--ticket", args.ticket, "--files", *args.files]
    if args.repo:
        command += ["--repo", args.repo]
    command += ["--local", *local_dirs(args.local), *args.extra]
    try:
        done = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=args.timeout)
    except FileNotFoundError:
        return 2, "pixi is not on PATH, so the architecture CLI cannot run"
    except subprocess.TimeoutExpired:
        return 2, f"the architecture CLI did not answer within {args.timeout} s"
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def verdict(ticket: str, status: int, output: str) -> tuple[int, str]:
    """`(exit status, the one line the orchestrator acts on)`."""
    heading = PLACED.search(output)
    placed = f" ({heading.group(1)} files on {heading.group(2)} components)" if heading else ""
    if status == 0:
        return 0, f"LAUNCH {ticket}: meets no other work{placed}"
    if status == 1:
        meets = MEET.findall(output)
        if meets:
            # The CLI repeats a meet on every component it touches; name each side once.
            others = sorted({name for _, detail in meets if detail.startswith("no blocking edge")
                             for name in TICKET.findall(detail) if name != ticket})
            parts = []
            if others:
                parts.append("no blocking edge links it to " + ", ".join(others[:3])
                             + (f" and {len(others) - 3} more" if len(others) > 3 else ""))
            if any(kind == "UNLINKABLE" for kind, _ in meets):
                parts.append("an epic's integration branch is in the meet, which no blocking edge can link")
            return 1, f"STOP {ticket}: meets live work — {'; '.join(parts) or 'no blocking edge coordinates it'}. Ask the user"
    reason = REASON.search(output)
    why = reason.group(1) if reason else (output.strip().splitlines() or ["no output from the CLI"])[-1]
    return 2, f"UNCHECKED {ticket}: {why[:300]} — say so to the user once, then launch"


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="preflight.py", description=__doc__.split("\n")[0])
    parser.add_argument("--ticket", required=True, type=ticket_label,
                        help="the lane's ticket in the map's form (repo#n; owner/repo#n is cut to it)")
    parser.add_argument("--files", required=True, nargs="+", metavar="PATH",
                        help="the files the ticket will touch, from the repository's root")
    parser.add_argument("--stores", default=None, help=f"opengwasdb-stores checkout (default: $ORCH_STORES, {DEFAULT_STORES})")
    parser.add_argument("--local", nargs="+", default=[], metavar="GIT_DIR",
                        help="clones whose local branches count (default: " + ", ".join(str(p) for p in DEFAULT_LOCAL) + ")")
    parser.add_argument("--repo", choices=("engine", "registry"), default=None,
                        help="the ticket's repository, so its paths are read against that repository's claims")
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for the map (default: 900)")
    parser.add_argument("extra", nargs="*", help="further `conflicts` flags, after `--`")
    args = parser.parse_args(argv)
    status, output = run(args)
    if output.strip():
        print(output.rstrip())
    status, line = verdict(args.ticket, status, output)
    print(line)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
