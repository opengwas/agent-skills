#!/usr/bin/env python3
"""Run orchestration lanes in Herdr: one tab per ticket, implementer and reviewer side by side.

Layout, all in the orchestrator's own Herdr workspace:
  - the orchestrator's tab is renamed `orch - <epic name>` (`init`);
  - each ticket gets a tab labelled for it (e.g. `#283 freeze`), with two panes:
      left:  the implementer, an interactive agent that keeps its context across fix rounds;
      right: the reviewer pane, where each review round runs both axes (Standards, Spec)
             as parallel one-shot reviewer processes, so the axes stay independent.

Subcommands (start, prompt and review block until the lane settles, so run them with
run_in_background):

  lane.py init    <run-dir> <epic name>
  lane.py start   <run-dir> <ticket> <tab label> <harness> <model> <cwd> <brief> [-- agent args]
  lane.py prompt  <run-dir> <ticket> <brief>        a follow-up (fix list) to the same implementer
  lane.py adopt   <run-dir> <ticket> <tab label> <cwd>   a ticket tab for an implementer running elsewhere
  lane.py review  <run-dir> <ticket> <harness> <model> <standards brief> <spec brief>
  lane.py wait    <run-dir> <ticket>               re-attach to a working implementer until it settles
  lane.py status  <run-dir> [<ticket>]
  lane.py tail    <run-dir> <ticket> [impl|review] [lines]
  lane.py stop    <run-dir> <ticket>               close the ticket's tab (only tabs this run made)
  lane.py cleanup <run-dir>                        close every ticket tab this run made

<harness> is `pi` (any pi model: deepseek/deepseek-flash, openai-codex/gpt-6.1-sol, ...) or
`claude` (Claude Code: claude-haiku-5-5, sonnet, opus). Workers write their report to
<run-dir>/reports/<ticket>.md and reviewers to <run-dir>/reviews/<ticket>-{standards,spec}.md.
Files are the reliable channel; reading the TUI viewport is not.

Must run inside a Herdr pane (HERDR_ENV=1).
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import subprocess
import time
import sys
from pathlib import Path

TDD_SKILL = Path.home() / ".agents/skills/tdd"
CLAUDE_PERMISSION_MODE = os.environ.get("ORCH_CLAUDE_PERMISSION_MODE", "auto")
SUSPECT = re.compile(
    r"(401|402|403|429|quota|credit|expired|rate.?limit|usage limit|session limit|"
    r"insufficient|billing|overloaded|authentication_error|extra usage)",
    re.IGNORECASE,
)


def herdr(*args: str, check: bool = True) -> dict:
    proc = subprocess.run(["herdr", *args], capture_output=True, text=True)
    out = proc.stdout.strip() or proc.stderr.strip()
    if check and proc.returncode != 0:
        sys.exit(f"herdr {' '.join(args[:3])} failed: {out[:500]}")
    try:
        return json.loads(out) if out else {}
    except json.JSONDecodeError:
        return {"raw": out, "returncode": proc.returncode}


def text_of(result: dict) -> str:
    return str(result.get("result", {}).get("text") or result.get("raw", ""))


def agent_name(ticket: str) -> str:
    """Herdr agent names are [a-z][a-z0-9_-]{0,31}: `impl-283`, `impl-t1`."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", ticket.lower()).strip("-") or "x"
    return f"impl-{slug}"[:32]


def layout_path(run_dir: Path) -> Path:
    return run_dir / "herdr.json"


_LOCK = None


def load_layout(run_dir: Path) -> dict:
    """Read herdr.json, taking an exclusive lock that save_layout releases.

    Lanes start concurrently in the background; without the lock, two starts each load
    the file and the second save drops the first lane's entry. A read-only command holds
    the lock only until it exits.
    """
    global _LOCK
    if _LOCK is None:
        _LOCK = open(run_dir / "herdr.json.lock", "w")
        fcntl.flock(_LOCK, fcntl.LOCK_EX)
    path = layout_path(run_dir)
    return json.loads(path.read_text()) if path.exists() else {"tickets": {}}


def save_layout(run_dir: Path, layout: dict) -> None:
    global _LOCK
    layout_path(run_dir).write_text(json.dumps(layout, indent=2) + "\n")
    if _LOCK is not None:
        fcntl.flock(_LOCK, fcntl.LOCK_UN)
        _LOCK.close()
        _LOCK = None


def pointer(brief: str, report: Path) -> str:
    return (f"Read {brief} and do what it says. When you are finished, write your report to "
            f"{report} as the brief describes, and reply with only that path.")


def suspects(pane_or_agent: str, *, agent: bool) -> list[str]:
    kind = "agent" if agent else "pane"
    out = herdr(kind, "read", pane_or_agent, "--source", "recent-unwrapped", "--lines", "120", check=False)
    return [line.strip() for line in text_of(out).splitlines() if SUSPECT.search(line)][-5:]


def settle_summary(run_dir: Path, ticket: str, result: dict) -> int:
    name = agent_name(ticket)
    status = result.get("result", {}).get("agent", {}).get("agent_status", "unknown")
    report = run_dir / "reports" / f"{ticket}.md"
    present = report.exists() and report.stat().st_size > 0
    print(f"LANE {ticket} implementer settled: status={status} report={'present' if present else 'MISSING'} ({report})")
    if not present or status == "blocked":
        for line in suspects(name, agent=True):
            print(f"SUSPECT {ticket}: {line[:200]}")
        if status == "blocked":
            print(f"BLOCKED {ticket}: inspect with `lane.py tail {run_dir} {ticket}` before answering anything")
    return 0 if present else 3


def init(run_dir: Path, epic_name: str) -> int:
    tab = os.environ["HERDR_TAB_ID"]
    herdr("tab", "rename", tab, f"orch - {epic_name}"[:60])
    layout = load_layout(run_dir)
    layout.update({"workspace": os.environ["HERDR_WORKSPACE_ID"], "orch_tab": tab})
    save_layout(run_dir, layout)
    print(f"orchestrator tab {tab} is 'orch - {epic_name}'")
    return 0


def start(run_dir: Path, ticket: str, label: str, harness: str, model: str, cwd: str, brief: str,
          extra: list[str]) -> int:
    for sub in ("reports", "reviews"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    layout = load_layout(run_dir)
    if ticket in layout["tickets"]:
        sys.exit(f"ticket {ticket} already has tab {layout['tickets'][ticket]['tab']}; use `prompt`, or `stop` it first")
    workspace = layout.get("workspace") or os.environ["HERDR_WORKSPACE_ID"]
    made = herdr("tab", "create", "--workspace", workspace, "--cwd", cwd, "--label", label[:40], "--no-focus")["result"]
    impl = made["root_pane"]["pane_id"]
    review = herdr("pane", "split", impl, "--direction", "right", "--cwd", cwd, "--no-focus")["result"]["pane"]["pane_id"]
    herdr("pane", "rename", impl, f"impl · {model}"[:40], check=False)
    herdr("pane", "rename", review, "review"[:40], check=False)
    layout["tickets"][ticket] = {"tab": made["tab"]["tab_id"], "label": label, "impl": impl, "review": review,
                                 "cwd": cwd, "harness": harness, "model": model, "review_rounds": 0}
    save_layout(run_dir, layout)
    if harness == "pi":
        args = ["--model", model, "--thinking", "high"]
        if TDD_SKILL.exists():
            args += ["--skill", str(TDD_SKILL)]
    elif harness == "claude":
        args = ["--model", model, "--permission-mode", CLAUDE_PERMISSION_MODE]
    else:
        sys.exit(f"unknown harness {harness!r}: use pi or claude")
    name = agent_name(ticket)
    # A fresh tab's shell can still be starting (the user's profile runs first); Herdr then
    # refuses with "not an available shell". Retry for up to a minute rather than fail.
    for _ in range(30):
        started = herdr("agent", "start", name, "--kind", harness, "--pane", impl, "--timeout", "90000",
                        "--", *args, *extra, check=False)
        if "not an available shell" not in json.dumps(started.get("error", "")):
            break
        time.sleep(2)
    if "error" in started:
        screen = text_of(herdr("agent", "read", name, "--source", "recent-unwrapped", "--lines", "40", check=False))
        if "trust this folder" in screen:
            # Claude Code asks once per new directory. That is the user's call: ask them once
            # per run (the worktrees are their repo), then accept and re-prompt.
            print(f"TRUST {ticket}: Claude Code asks whether to trust {cwd}. With the user's OK, run\n"
                  f"  herdr agent send-keys {name} down enter && lane.py prompt {run_dir} {ticket} {brief}")
        else:
            print(f"NOT-READY {ticket}: {started['error'].get('message', started['error'])}; "
                  f"inspect with `lane.py tail {run_dir} {ticket}`")
        return 4
    result = herdr("agent", "prompt", name, pointer(brief, run_dir / "reports" / f"{ticket}.md"), "--wait", check=False)
    return settle_summary(run_dir, ticket, result)


def adopt(run_dir: Path, ticket: str, label: str, cwd: str) -> int:
    """A ticket tab for work whose implementer runs elsewhere (e.g. an in-session agent):
    the tab and both panes exist, so its review runs in Herdr like any other ticket's."""
    layout = load_layout(run_dir)
    if ticket in layout["tickets"]:
        sys.exit(f"ticket {ticket} already has tab {layout['tickets'][ticket]['tab']}")
    workspace = layout.get("workspace") or os.environ["HERDR_WORKSPACE_ID"]
    made = herdr("tab", "create", "--workspace", workspace, "--cwd", cwd, "--label", label[:40], "--no-focus")["result"]
    impl = made["root_pane"]["pane_id"]
    review = herdr("pane", "split", impl, "--direction", "right", "--cwd", cwd, "--no-focus")["result"]["pane"]["pane_id"]
    herdr("pane", "rename", impl, "impl · elsewhere", check=False)
    herdr("pane", "rename", review, "review", check=False)
    layout["tickets"][ticket] = {"tab": made["tab"]["tab_id"], "label": label, "impl": impl, "review": review,
                                 "cwd": cwd, "harness": "external", "model": "external", "review_rounds": 0}
    save_layout(run_dir, layout)
    print(f"ticket {ticket} adopted in tab {made['tab']['tab_id']} ({label})")
    return 0


def prompt(run_dir: Path, ticket: str, brief: str) -> int:
    result = herdr("agent", "prompt", agent_name(ticket), pointer(brief, run_dir / "reports" / f"{ticket}.md"),
                   "--wait", check=False)
    return settle_summary(run_dir, ticket, result)


def reviewer_command(harness: str, model: str, brief: str, out: Path) -> str:
    message = (f"Read {brief} and do what it says. Write your review to {out} as the brief describes, "
               f"and reply with only that path.")
    if harness == "pi":
        cmd = ["pi", "-p", "--model", model, "--no-session", "--thinking", "high", message]
    elif harness == "claude":
        cmd = ["claude", "-p", "--model", model, "--permission-mode", CLAUDE_PERMISSION_MODE, message]
    else:
        sys.exit(f"unknown harness {harness!r}: use pi or claude")
    return shlex.join(cmd)


def review(run_dir: Path, ticket: str, harness: str, model: str, standards: str, spec: str) -> int:
    """Both axes in parallel, as separate one-shot processes in the ticket's review pane."""
    layout = load_layout(run_dir)
    lane = layout["tickets"][ticket]
    lane["review_rounds"] += 1
    rnd = lane["review_rounds"]
    save_layout(run_dir, layout)
    outs = {axis: run_dir / "reviews" / f"{ticket}-{axis}.md" for axis in ("standards", "spec")}
    for out in outs.values():
        out.unlink(missing_ok=True)
    marker = f"REVIEW-DONE {ticket} round {rnd}"
    script = run_dir / "reviews" / f"{ticket}-round{rnd}.sh"
    logs = {axis: run_dir / "reviews" / f"{ticket}-{axis}-round{rnd}.log" for axis in outs}
    script.write_text("\n".join([
        "#!/usr/bin/env bash",
        f"cd {shlex.quote(lane['cwd'])}",
        f"echo 'review round {rnd} of {ticket} on {model}: standards and spec in parallel'",
        f"{reviewer_command(harness, model, standards, outs['standards'])} > {shlex.quote(str(logs['standards']))} 2>&1 &",
        f"{reviewer_command(harness, model, spec, outs['spec'])} > {shlex.quote(str(logs['spec']))} 2>&1 &",
        "wait",
        *[f"echo '{axis}:' $(test -s {shlex.quote(str(out))} && echo written || echo MISSING)"
          for axis, out in outs.items()],
        f"echo '{marker}'",
        "",
    ]))
    herdr("pane", "rename", lane["review"], f"review r{rnd} · {model}"[:40], check=False)
    herdr("pane", "run", lane["review"], f"bash {shlex.quote(str(script))}")
    herdr("pane", "wait-output", lane["review"], "--match", marker, "--source", "recent-unwrapped", check=False)
    missing = [axis for axis, out in outs.items() if not (out.exists() and out.stat().st_size > 0)]
    print(f"REVIEW {ticket} round {rnd} settled: " + ", ".join(
        f"{axis}={'present' if axis not in missing else 'MISSING'}" for axis in outs))
    for axis in missing:
        log = logs[axis].read_text(errors="replace") if logs[axis].exists() else ""
        for line in [l.strip() for l in log.splitlines() if SUSPECT.search(l)][-3:]:
            print(f"SUSPECT {ticket} {axis}: {line[:200]}")
    return 0 if not missing else 3


def main(argv: list[str]) -> int:
    if os.environ.get("HERDR_ENV") != "1":
        sys.exit("not running inside a Herdr pane (HERDR_ENV != 1); lanes need Herdr")
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, run_dir = argv[0], Path(argv[1]).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    rest = argv[2:]
    if cmd == "init":
        return init(run_dir, " ".join(rest))
    if cmd == "start":
        extra = rest[rest.index("--") + 1:] if "--" in rest else []
        rest = rest[: rest.index("--")] if "--" in rest else rest
        return start(run_dir, *rest, extra=extra)
    if cmd == "prompt":
        return prompt(run_dir, *rest)
    if cmd == "adopt":
        return adopt(run_dir, *rest)
    if cmd == "wait":
        # Re-attach to a lane whose start/prompt waiter died (e.g. a timeout around it).
        result = herdr("agent", "wait", agent_name(rest[0]), check=False)
        return settle_summary(run_dir, rest[0], result)
    if cmd == "review":
        return review(run_dir, *rest)
    layout = load_layout(run_dir)
    if cmd == "status":
        for ticket in rest or list(layout["tickets"]):
            lane = layout["tickets"].get(ticket, {})
            agent = herdr("agent", "get", agent_name(ticket), check=False).get("result", {}).get("agent", {})
            print(f"{ticket}\t{lane.get('tab', '?')} {lane.get('label', '')}\timplementer={agent.get('agent_status', 'gone')}"
                  f"\treview_rounds={lane.get('review_rounds', 0)}")
        return 0
    if cmd == "tail":
        ticket, which = rest[0], (rest[1] if len(rest) > 1 else "impl")
        lines = rest[2] if len(rest) > 2 else "80"
        if which == "review":
            out = herdr("pane", "read", layout["tickets"][ticket]["review"], "--source", "recent-unwrapped",
                        "--lines", lines, check=False)
        else:
            out = herdr("agent", "read", agent_name(ticket), "--source", "recent-unwrapped", "--lines", lines, check=False)
        print(text_of(out))
        return 0
    if cmd == "stop":
        lane = layout["tickets"].pop(rest[0])
        herdr("tab", "close", lane["tab"], check=False)
        save_layout(run_dir, layout)
        return 0
    if cmd == "cleanup":
        for lane in layout["tickets"].values():
            herdr("tab", "close", lane["tab"], check=False)
        layout["tickets"] = {}
        save_layout(run_dir, layout)
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
