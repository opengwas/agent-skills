#!/usr/bin/env python3
"""Does this ticket's lane meet uncoordinated live work? Ask the architecture map before launching it.

    preflight.py --ticket <repo#n> --files <path>... [--stores DIR] [--local GIT_DIR...]
                 [--repo engine|registry] [--timeout S] [-- <architecture conflicts flags>]

Run from anywhere. It runs `conflicts --refresh` from the architecture CLI (#419, epic #416) in an
opengwasdb-stores checkout: `--stores`, else `$ORCH_STORES`, else `~/repo/opengwasdb-stores`.
`--refresh` fetches the engine and both repositories' branches before the map answers. It passes
`--local` the host's own clones (`~/repo/opengwasdb`, `~/repo/opengwasdb-stores`, when
they exist) so that lanes which exist only on this host count. The files are the ones the
ticket's notes and its brief assign it, spelled as the repository spells them. The ticket is
the map's (`opengwasdb#338`); an `owner/repo#n` label is accepted and cut to that form.

Prints the CLI's own output, then one verdict line and its action as the exit status:

  LAUNCH     0  it said the files meet no other live work, or only coordinated work. Launch.
  STOP       1  it said the files meet other work; the verdict names it. Stop and ask the user.
               Exit 1 is a conflict even when its output cannot be read: asking is cheap.
  UNCHECKED  2  it did not answer: exit 2, a timeout, an unexpected exit status, output that
               contradicts itself, or a missing checkout or CLI. Say so once, then launch.

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
OWNER = re.compile(r"^  (\S+#\d+)(?:\s|$)")
BRANCH = re.compile(r"([A-Za-z0-9_.-]+:[A-Za-z0-9_./-]+) belongs to an epic as a whole")
PLACED = re.compile(r"(\d+) files on (\d+) components")
CLEAR = re.compile(r"^meets no other work$", re.MULTILINE)
COORDINATED = re.compile(r"^    coordinated: ", re.MULTILINE)
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
    # `--refresh` fetches the engine and both repositories' branches first; without it the map
    # answers from whatever was last fetched, and misses a branch pushed since.
    command = ["pixi", "run", "-e", "dev", "architecture", "conflicts", "--refresh",
               "--ticket", args.ticket, "--files", *args.files]
    if args.repo:
        command += ["--repo", args.repo]
    local = local_dirs(args.local)
    if local:
        command += ["--local", *local]
    command += args.extra
    try:
        done = subprocess.run(command, cwd=directory, capture_output=True, text=True, errors="replace",
                              timeout=args.timeout)
    except subprocess.TimeoutExpired:
        return 2, f"the architecture CLI did not answer within {args.timeout} s"
    except OSError as error:
        return 2, f"the architecture CLI could not run: {error}"
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def unlinkable(output: str) -> list[str]:
    """`branch (epic repo#n)` for each UNLINKABLE line, married to the owner heading above it."""
    found, epic = [], ""
    for line in output.splitlines():
        if not line.startswith("    ") and (heading := OWNER.match(line)):
            epic = heading.group(1)
        for branch in BRANCH.findall(line):
            found.append(f"{branch} (epic {epic})" if epic else branch)
    return sorted(set(found))


def tail(output: str) -> str:
    return (output.strip().splitlines() or ["no output from the CLI"])[-1].strip()


def verdict(ticket: str, status: int, output: str) -> tuple[int, str]:
    """`(exit status, the one line the orchestrator acts on)`."""
    heading = PLACED.search(output)
    placed = f" ({heading.group(1)} files on {heading.group(2)} components)" if heading else ""
    reason = REASON.search(output)
    decided = f"it cannot decide: {reason.group(1)[:200]}" if reason else ""
    if status == 0:
        if reason or MEET.search(output):
            return 2, f"UNCHECKED {ticket}: the map exited 0 but says {decided or 'it found a conflict'}"
        if CLEAR.search(output):
            return 0, f"LAUNCH {ticket}: meets no other work{placed}"
        if COORDINATED.search(output):
            return 0, f"LAUNCH {ticket}: meets only coordinated work{placed}"
        return 2, f"UNCHECKED {ticket}: the map exited 0 but did not say whether the files meet other " \
                  f"work: {tail(output)[:200]}"
    if status == 1:
        meets = MEET.findall(output)
        # The CLI repeats a meet on every component it touches; name each side once.
        others = sorted({name for _, detail in meets if detail.startswith("no blocking edge")
                         for name in TICKET.findall(detail) if name != ticket})
        parts = []
        if others:
            parts.append("no blocking edge links it to " + ", ".join(others[:3])
                         + (f" and {len(others) - 3} more" if len(others) > 3 else ""))
        branches = unlinkable(output)
        if branches:
            parts.append("an epic's branch takes no blocking edge: " + ", ".join(branches[:3]))
        if not parts:
            parts.append("the map reported a conflict it couldn't describe; ask the user and show its "
                         f"output: {tail(output)[:200]}")
        return 1, f"STOP {ticket}: meets live work — {'; '.join(parts)}. Ask the user"
    if status == 2:
        return 2, f"UNCHECKED {ticket}: {reason.group(1)[:300] if reason else tail(output)[:300]}"
    return 2, f"UNCHECKED {ticket}: the map exited {status}, which it does not define: {tail(output)[:200]}"


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="preflight.py", description=__doc__.split("\n")[0])
    parser.add_argument("--ticket", required=True, type=ticket_label,
                        help="the lane's ticket in the map's form (repo#n; owner/repo#n is cut to it)")
    parser.add_argument("--files", required=True, nargs="+", metavar="PATH",
                        help="the files the ticket will touch, from the repository's root")
    parser.add_argument("--stores", default=None, help=f"opengwasdb-stores checkout (default: $ORCH_STORES, {DEFAULT_STORES})")
    parser.add_argument("--local", nargs="+", default=[], metavar="GIT_DIR",
                        help="clones whose local branches count (default: the ones that exist of "
                             + ", ".join(str(p) for p in DEFAULT_LOCAL) + ")")
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
