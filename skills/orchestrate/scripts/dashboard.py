#!/usr/bin/env python3
"""Render <run-dir>/state.json into the draft PR's dashboard body.

  dashboard.py <run-dir>            print the Markdown body
  dashboard.py <run-dir> --apply    also `gh pr edit <pr> --body-file`, in the state's repo

state.json shape (keep it this small; it is re-read on every resume):

{
  "repo": "owner/name", "epic": 282, "title": "...", "base": "dev",
  "integration_branch": "orch/282-manifest-pipeline", "pr": 300,
  "board_note": "stage 2 waits on #222",   (optional; appended to the epic's Next on the board)
  "models": {"implementer": ["deepseek/deepseek-flash", ...], "reviewer": [...], "dead": {"model": "why"}},
  "tickets": {
    "283": {"title": "...", "status": "merged", "blocked_by": ["249"], "lane": "t283",
            "model": "deepseek/deepseek-flash", "branch": "orch/282/283", "review": "2 rounds",
            "merge": "abc1234", "note": "re-freeze byte-identical"}
  },
  "seams": {"283": ["Source Metadata Table loading refuses unknown columns", "..."]},
  "decisions": [{"when": "2026-10-16", "ticket": "286", "decision": "...", "by": "user|orchestrator"}],
  "questions": ["open questions for the user"],
  "waiting_external": {"289": "OGS-00009 2.5k landing (#222)"},
  "followups": ["opengwas/opengwasdb#284 build_besd strand lift"],
  "test_time": {"baseline": {"wall_s": 714, "commit": "abc1234"},
                "merges": [{"ticket": "283", "commit": "def5678", "wall_s": 731, "note": "freeze suites +12 s"}],
                "final": {"wall_s": 760}}
}
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ORDER = ["implementing", "fixing", "reviewing", "needs-decision", "frontier", "waiting-external", "blocked", "merged"]
ICON = {"merged": "✅", "implementing": "🔨", "fixing": "🔧", "reviewing": "🔍", "frontier": "🟢",
        "needs-decision": "❓", "waiting-external": "⏳", "blocked": "⛔"}


def render(state: dict) -> str:
    tickets = state.get("tickets", {})
    counts = {s: sum(1 for t in tickets.values() if t.get("status") == s) for s in ORDER}
    done = counts["merged"]
    lines = [
        f"Orchestrating #{state['epic']}: {state.get('title', '')}",
        "",
        f"**{done}/{len(tickets)} tickets merged** into `{state['integration_branch']}`. "
        + ", ".join(f"{counts[s]} {s}" for s in ORDER if counts[s] and s != "merged"),
        "",
        "| Ticket | Status | Lane · model | Review | Merged | Note |",
        "|---|---|---|---|---|---|",
    ]
    def key(item):
        number, ticket = item
        status = ticket.get("status", "blocked")
        return (ORDER.index(status) if status in ORDER else len(ORDER), number)
    for number, t in sorted(tickets.items(), key=key):
        status = t.get("status", "blocked")
        lane = " · ".join(x for x in (t.get("lane"), t.get("model")) if x)
        lines.append(f"| #{number} {t.get('title', '')[:60]} | {ICON.get(status, '')} {status} | {lane} "
                     f"| {t.get('review', '')} | {t.get('merge', '')} | {t.get('note', '')} |")
    if state.get("questions"):
        lines += ["", "### Waiting on you", *[f"- {q}" for q in state["questions"]]]
    if state.get("waiting_external"):
        lines += ["", "### Waiting on something outside this run",
                  *[f"- #{n}: {why}" for n, why in state["waiting_external"].items()]]
    if state.get("seams"):
        lines += ["", "<details><summary>Agreed test seams (object on the ticket if one is wrong)</summary>", ""]
        for number, seams in state["seams"].items():
            lines += [f"**#{number}**", *[f"- {s}" for s in seams], ""]
        lines.append("</details>")
    if state.get("decisions"):
        lines += ["", "### Decisions", "| When | Ticket | Decision | By |", "|---|---|---|---|"]
        lines += [f"| {d.get('when', '')} | #{d.get('ticket', '')} | {d['decision']} | {d.get('by', '')} |"
                  for d in state["decisions"]]
    timing = state.get("test_time", {})
    if timing.get("baseline"):
        base = timing["baseline"]["wall_s"]
        def delta(wall):
            return f"{wall:.0f} s ({(wall - base) / base:+.0%})"
        lines += ["", "### Test time", f"- Baseline (`{timing['baseline'].get('commit', '')}`): {base:.0f} s"]
        lines += [f"- After #{m['ticket']} (`{m.get('commit', '')}`): {delta(m['wall_s'])}"
                  + (f": {m['note']}" if m.get("note") else "") for m in timing.get("merges", [])]
        if timing.get("final"):
            lines.append(f"- **Final:** {delta(timing['final']['wall_s'])}")
    if state.get("followups"):
        lines += ["", "### Follow-ups filed", *[f"- {f}" for f in state["followups"]]]
    models = state.get("models", {})
    if models:
        lines += ["", "<details><summary>Models</summary>", "",
                  f"- Implementers: {', '.join(models.get('implementer', []))}",
                  f"- Reviewers: {', '.join(models.get('reviewer', []))}",
                  *[f"- Dead: `{m}`: {why}" for m, why in models.get("dead", {}).items()], "", "</details>"]
    lines += ["", f"_Tickets close as they merge into `{state.get('integration_branch')}`, "
                  "and are reopened if the final review sends them back._"]
    lines += ["", f"_Updated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by the orchestrator._"]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if not argv:
        sys.exit(__doc__)
    state = json.loads((Path(argv[0]) / "state.json").read_text())
    body = render(state)
    if "--apply" in argv:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write(body)
        subprocess.run(["gh", "pr", "edit", str(state["pr"]), "--repo", state["repo"],
                        "--body-file", handle.name], check=True)
        print(f"dashboard applied to {state['repo']}#{state['pr']}")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
