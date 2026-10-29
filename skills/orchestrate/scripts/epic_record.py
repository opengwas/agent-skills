#!/usr/bin/env python3
"""Build the epic record of a finished run, for a repo with a project site.

  epic_record.py <run-dir> --summary-file F [--out PATH]

The record is docs/_epics/<repo>-<n>.yaml in opengwasdb-stores' docs/spec/project-site.md.
It is built from <run-dir>/state.json, and from the state-stage*.json archives beside
it (earlier stages first; a ticket a later stage re-entered replaces its earlier entry).
The summary (2-4 sentences) is written by the orchestrator and read from F, never made up.

An unknown value is null, never an estimate. Optional state.json keys, all verbatim:
  workstream, started, finished (a date: the epic issue closed; else status is active),
  versions, yardstick {before, after}, catalog {before, after}.
Tickets: an entry's `issue`, else its key (`386` -> <repo>#386, `odb333`/`ogdb302` ->
opengwasdb#n), else null. `merge` is the first commit hash in `merge` or `merge_commit`.

Standard library only. It does not validate: run the repo's validator on the result.
"""
import json
import re
import sys
from pathlib import Path

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX = re.compile(r"^[0-9a-fA-F]{7,40}(?![0-9A-Za-z_])")
REF = re.compile(r"(?:[\w.-]+/)?([\w.-]+)?#(\d+)")
SIBLING = re.compile(r"^(?:odb|ogdb)(\d+)$")
PLAIN = re.compile(r"[A-Za-z][A-Za-z0-9_./#-]*( [A-Za-z0-9_./-][A-Za-z0-9_./#-]*)*\Z")
UNSAFE = re.compile("[\x7f-\x9f\u2028\u2029\ufeff]")
RESERVED = {"null", "true", "false", "yes", "no", "on", "off", "y", "n"}


def ref(text, repo):
    """`opengwas/opengwasdb#333`, `opengwasdb#333` or `#333` -> repo#n, else None."""
    m = REF.match(str(text).strip()) if text is not None else None
    return f"{m.group(1) or repo}#{m.group(2)}" if m else None


def commit(*values):
    for v in values:
        m = HEX.match(str(v).strip()) if v else None
        if m:
            return m.group(0).lower()
    return None


def number(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def load_states(run):
    run = Path(run)
    return [json.loads(p.read_text()) for p in sorted(run.glob("state-stage*.json"))] + [
        json.loads((run / "state.json").read_text())]


def ticket_key(k, entry, repo):
    if entry.get("issue"):
        return ref(entry["issue"], repo)
    if k.isdigit():
        return f"{repo}#{k}"
    m = SIBLING.match(k)
    return f"opengwasdb#{m.group(1)}" if m else None


def tickets(states, repo):
    rows = {}
    for s in states:
        for k, e in s["tickets"].items():
            rows[k] = {"key": ticket_key(k, e, repo), "title": e.get("title") or k,
                       "pr": ref(e.get("pr"), repo) if e.get("pr") else None,
                       "merge": commit(e.get("merge"), e.get("merge_commit"))}
    return list(rows.values())


def prs(states, repo, rows):
    out = []
    for s in states:
        found = [ref(k, repo) for k in (s.get("pr_merged") or {})]
        found += [f"{repo}#{s['pr']}"] if s.get("pr") else []
        out += found
    out += [r["pr"] for r in rows if r["pr"]]
    return list(dict.fromkeys(out))


def decisions(states):
    out = {}
    for s in states:
        for d in s["decisions"]:
            when = str(d.get("when") or d.get("date") or "")[:10]
            if not ISO.match(when):
                sys.exit(f"decision has no ISO date: {str(d)[:100]}")
            out.setdefault((when, d["decision"]), {"date": when, "text": d["decision"], "link": None})
    return list(out.values())


def test_run(run):
    if not isinstance(run, dict):
        return None
    suites = run.get("suites")
    if isinstance(suites, dict):
        suites = {k: number(v) for k, v in suites.items()}
    else:
        suites = None
    return {"commit": commit(run.get("commit")), "wall_s": number(run.get("wall_s")), "suites": suites}


def followups(state, repo):
    out = []
    for f in state.get("followups") or []:
        if isinstance(f, dict):
            text = f.get("title") or ""
            key = ref(f["issue"], repo) if f.get("issue") else ref(text, repo)
        else:
            text, key = str(f), ref(f, repo)
        if text.strip():
            out.append({"key": key, "text": text.strip()})
    return out


def pair(v):
    v = v if isinstance(v, dict) else {}
    return {"before": v.get("before"), "after": v.get("after")}


def record(run, summary):
    states = load_states(run)
    last = states[-1]
    repo = last["repo"].split("/")[-1]
    rows = tickets(states, repo)
    dates = sorted(d["date"] for d in decisions(states))
    tt = last.get("test_time") or {}
    return {
        "repo": repo,
        "number": last["epic"],
        "title": last["title"],
        "status": "finished" if last.get("finished") else "active",
        "workstream": last.get("workstream"),
        "started": last.get("started") or (dates[0] if dates else None),
        "finished": last.get("finished"),
        "summary": " ".join(summary.split()) or None,
        "prs": prs(states, repo, rows),
        "versions": last.get("versions") or [],
        "tickets": rows,
        "decisions": decisions(states),
        "test_time": {"baseline": test_run(tt.get("baseline")), "final": test_run(tt.get("final"))},
        "yardstick": pair(last.get("yardstick")),
        "catalog": pair(last.get("catalog")),
        "followups": followups(last, repo),
    }


def scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if PLAIN.match(v) and v.lower() not in RESERVED:
        return v
    return UNSAFE.sub(lambda m: "\\u%04x" % ord(m.group()), json.dumps(v, ensure_ascii=False))


def emit(v, indent=0, lines=None):
    """Block YAML in the committed layout: lists sit at their key's indent."""
    lines = [] if lines is None else lines
    pad = " " * indent
    for k, x in v.items():
        if isinstance(x, dict):
            lines.append(f"{pad}{scalar(k)}:")
            emit(x, indent + 2, lines)
        elif isinstance(x, list) and x:
            lines.append(f"{pad}{scalar(k)}:")
            for item in x:
                if isinstance(item, dict):
                    sub = emit(item, indent + 2, [])
                    lines.append(f"{pad}- {sub[0].strip()}")
                    lines += sub[1:]
                else:
                    lines.append(f"{pad}- {scalar(item)}")
        else:
            lines.append(f"{pad}{scalar(k)}: {'[]' if x == [] else scalar(x)}")
    return lines


def main(argv):
    args = list(argv)
    opts = {}
    for flag in ("--summary-file", "--out"):
        if flag in args:
            i = args.index(flag)
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 1 or "--summary-file" not in opts:
        sys.exit(__doc__)
    rec = record(args[0], Path(opts["--summary-file"]).read_text())
    text = "\n".join(emit(rec)) + "\n"
    if "--out" in opts:
        Path(opts["--out"]).parent.mkdir(parents=True, exist_ok=True)
        Path(opts["--out"]).write_text(text)
        print(opts["--out"])
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
