#!/usr/bin/env python3
"""Snapshot, check and update the OpenGWASDB project board.

  board.py report [--stale-days N]   print the sync report (and cache the snapshot)
  board.py apply CHANGES.json [--dry-run]
  board.py post-update --status ON_TRACK|AT_RISK|OFF_TRACK|COMPLETE|INACTIVE --body-file F
  board.py set KEY Field=Value ...    set board fields, adding the item if missing
  board.py sync-run RUN_DIR [--note TEXT]
                                     make an orchestrate run's state.json true on GitHub

The board's conventions live in its README; this script only measures the
board against them and applies changes a human approved.
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

OWNER = "opengwas"
PROJECT = 1
REPOS = ["opengwasdb", "opengwasdb-stores"]
CACHE = os.path.expanduser("~/.cache/board")
RUN_DIRS = [os.path.expanduser("~/.cache/orchestrate")]
EPIC_LABELS = {"complexity:epic", "epic"}


# ---------------------------------------------------------------- gh

def gh(*args, stdin=None):
    r = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"gh {' '.join(args[:3])} failed: {r.stderr.strip()}")
    return r.stdout


def graphql(query, **variables):
    out = gh("api", "graphql", "--input", "-",
             stdin=json.dumps({"query": query, "variables": variables}))
    data = json.loads(out)
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]


def key(repo_with_owner, number):
    return f"{repo_with_owner.split('/')[-1]}#{number}"


def parse_key(k):
    repo, n = k.split("#")
    return repo, int(n)


# ---------------------------------------------------------- snapshot

ISSUE_FIELDS = """
  number title url state createdAt updatedAt closedAt
  repository { nameWithOwner }
  issueType { name }
  labels(first: 20) { nodes { name } }
  parent { number state repository { nameWithOwner } }
  subIssuesSummary { total completed }
"""

PROJECT_Q = """
query($owner: String!, $number: Int!, $cursor: String) {
  organization(login: $owner) { projectV2(number: $number) {
    id
    fields(first: 50) { nodes {
      ... on ProjectV2FieldCommon { id name dataType }
      ... on ProjectV2SingleSelectField { options { id name } }
    } }
    statusUpdates(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes { createdAt status body }
    }
    items(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        content {
          ... on Issue { %s body }
          ... on PullRequest { number title url state repository { nameWithOwner } }
        }
        fieldValues(first: 20) { nodes {
          ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
          ... on ProjectV2ItemFieldTextValue { text field { ... on ProjectV2FieldCommon { name } } }
        } }
      }
    }
  } }
}""" % ISSUE_FIELDS

ISSUES_Q = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, states: OPEN, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { %s }
    }
  }
}""" % ISSUE_FIELDS


def fetch_project():
    items, cursor, project = [], None, None
    while True:
        p = graphql(PROJECT_Q, owner=OWNER, number=PROJECT, cursor=cursor)["organization"]["projectV2"]
        project = project or p
        for node in p["items"]["nodes"]:
            c = node["content"]
            if not c or "number" not in c:
                continue
            values = {}
            for v in node["fieldValues"]["nodes"]:
                if v and v.get("field"):
                    values[v["field"]["name"]] = v.get("name", v.get("text"))
            items.append({"item_id": node["id"], "key": key(c["repository"]["nameWithOwner"], c["number"]),
                          "issue": c, "fields": values})
        if not p["items"]["pageInfo"]["hasNextPage"]:
            break
        cursor = p["items"]["pageInfo"]["endCursor"]
    fields = {f["name"]: f for f in project["fields"]["nodes"] if f}
    last = (project["statusUpdates"]["nodes"] or [None])[0]
    return {"id": project["id"], "fields": fields, "items": items, "last_update": last}


def fetch_open_issues():
    issues = {}
    for repo in REPOS:
        cursor = None
        while True:
            r = graphql(ISSUES_Q, owner=OWNER, name=repo, cursor=cursor)["repository"]["issues"]
            for i in r["nodes"]:
                issues[key(i["repository"]["nameWithOwner"], i["number"])] = i
            if not r["pageInfo"]["hasNextPage"]:
                break
            cursor = r["pageInfo"]["endCursor"]
    return issues


def fetch_refs(keys):
    """State and kind (Issue or PullRequest) of each repo#n, in aliased queries."""
    keys = sorted(set(keys))
    refs = {}
    for start in range(0, len(keys), 50):
        chunk = keys[start:start + 50]
        parts = []
        for i, k in enumerate(chunk):
            repo, n = parse_key(k)
            parts.append(f'k{i}: repository(owner: "{OWNER}", name: "{repo}") {{ issueOrPullRequest(number: {n}) {{'
                         f' __typename ... on Issue {{ state }} ... on PullRequest {{ state }} }} }}')
        data = graphql("query {" + "\n".join(parts) + "}")
        for i, k in enumerate(chunk):
            node = (data.get(f"k{i}") or {}).get("issueOrPullRequest")
            refs[k] = {"state": node["state"], "kind": node["__typename"]} if node else {"state": "MISSING", "kind": None}
    return refs


def fetch_states(keys):
    return {k: r["state"] for k, r in fetch_refs(keys).items()}


def read_runs():
    runs = []
    for d in RUN_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*", "state.json"))):
            try:
                s = json.load(open(path))
            except (OSError, ValueError):
                continue
            tickets = s.get("tickets", {})
            counts = {}
            for t in tickets.values():
                counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
            live = {k: {"status": t.get("status"), "title": t.get("title"), "note": t.get("note")}
                    for k, t in tickets.items() if t.get("status") not in ("merged", "blocked")}
            runs.append({"path": path, "repo": s.get("repo"), "epic": s.get("epic"), "pr": s.get("pr"),
                         "title": s.get("title"), "base": s.get("base"),
                         "modified": dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc).isoformat(),
                         "counts": counts, "live": live})
    return runs


# ------------------------------------------------------------ checks

def is_epic(issue):
    labels = {l["name"] for l in issue.get("labels", {}).get("nodes", [])}
    return ((issue.get("issueType") or {}).get("name") == "Epic" or bool(labels & EPIC_LABELS)
            or issue["title"].lower().startswith("epic:"))


def is_milestone(issue):
    return ((issue.get("issueType") or {}).get("name") == "Milestone"
            or issue["title"].lower().startswith("milestone:"))


REF = re.compile(r"(?:\b([\w.-]+)/([\w.-]+))?#(\d+)\b")


def checklist(body, home_repo):
    """Each `- [ ]` / `- [x]` line of a milestone body with the refs it names."""
    lines = []
    for line in (body or "").splitlines():
        m = re.match(r"\s*[-*] \[( |x|X)\] (.*)", line)
        if not m:
            continue
        refs = []
        for owner, repo, n in REF.findall(m.group(2)):
            if owner and owner != OWNER:
                continue
            refs.append(f"{repo or home_repo}#{n}")
        lines.append({"checked": m.group(1) != " ", "text": m.group(2).strip(), "refs": refs})
    return lines


def days_since(iso, now):
    return (now - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).days


def analyse(project, issues, runs, stale_days):
    now = dt.datetime.now(dt.timezone.utc)
    board = {i["key"]: i for i in project["items"]}
    open_board = {k for k, i in board.items() if i["issue"]["state"] == "OPEN"}
    runs_by_key = {key(r["repo"], r["epic"]): r for r in runs if r.get("repo") and r.get("epic")}
    drift = {"closed_not_done": [], "done_but_open": [], "no_workstream": [], "no_status": [],
             "stale_active": [], "tickets_on_board": [], "epics_off_board": [], "milestones_off_board": []}

    for k, it in board.items():
        iss, f = it["issue"], it["fields"]
        status = f.get("Status")
        if iss["state"] != "OPEN" and status != "Done":
            drift["closed_not_done"].append(k)
        if iss["state"] == "OPEN" and status == "Done":
            drift["done_but_open"].append(k)
        if iss["state"] != "OPEN":
            continue
        if not status:
            drift["no_status"].append(k)
        if not is_milestone(iss) and not f.get("Workstream"):
            drift["no_workstream"].append(k)
        parent = iss.get("parent")
        if parent and key(parent["repository"]["nameWithOwner"], parent["number"]) in open_board:
            drift["tickets_on_board"].append(k)
        if status == "Active":
            seen = [iss.get("updatedAt"), runs_by_key.get(k, {}).get("modified")]
            quiet = min((days_since(s, now) for s in seen if s), default=None)
            if quiet is not None and quiet >= stale_days:
                drift["stale_active"].append(f"{k} (quiet {quiet} d)")

    for k, iss in issues.items():
        if k in board:
            continue
        if is_milestone(iss):
            drift["milestones_off_board"].append(k)
        elif is_epic(iss):
            drift["epics_off_board"].append(k)

    # Inbox: open issues with no open ancestor (or self) on the board.
    def placed(k, seen=()):
        if k in open_board:
            return True
        p = (issues.get(k) or {}).get("parent")
        if not p or p["state"] != "OPEN" or k in seen:
            return False
        return placed(key(p["repository"]["nameWithOwner"], p["number"]), seen + (k,))

    since = (project["last_update"] or {}).get("createdAt")
    inbox = []
    for k, iss in issues.items():
        if placed(k) or is_epic(iss) or is_milestone(iss):
            continue
        p = iss.get("parent")
        inbox.append({"key": k, "title": iss["title"], "created": iss["createdAt"][:10],
                      "updated": iss["updatedAt"][:10], "new": bool(since and iss["createdAt"] > since),
                      "closed_parent": key(p["repository"]["nameWithOwner"], p["number"]) if p else None})
    inbox.sort(key=lambda i: i["created"], reverse=True)

    milestones = []
    ms_keys = [k for k in open_board if is_milestone(board[k]["issue"])]
    lines_by_ms = {k: checklist(board[k]["issue"].get("body"), parse_key(k)[0]) for k in ms_keys}
    states = fetch_states([r for ls in lines_by_ms.values() for l in ls for r in l["refs"]])
    for k in ms_keys:
        rows = []
        for l in lines_by_ms[k]:
            ref_states = {r: states.get(r, "?") for r in l["refs"]}
            all_done = bool(ref_states) and all(s in ("CLOSED", "MERGED") for s in ref_states.values())
            flag = ("tick?" if all_done and not l["checked"]
                    else "untick?" if l["checked"] and any(s == "OPEN" for s in ref_states.values())
                    else "")
            rows.append({**l, "ref_states": ref_states, "flag": flag})
        milestones.append({"key": k, "title": board[k]["issue"]["title"], "lines": rows})

    return {"generated": now.isoformat(), "last_update": project["last_update"], "drift": drift,
            "inbox": inbox, "milestones": milestones, "runs": runs,
            "threads": [{"key": k, "title": board[k]["issue"]["title"], **board[k]["fields"],
                         "progress": board[k]["issue"].get("subIssuesSummary"),
                         "updated": board[k]["issue"].get("updatedAt", "")[:10],
                         "run": runs_by_key.get(k, {}).get("path")}
                        for k in sorted(open_board) if not is_milestone(board[k]["issue"])]}


# ------------------------------------------------------------ report

def render(a):
    out = [f"# Board sync report ({a['generated'][:16]} UTC)", ""]
    lu = a["last_update"]
    out.append(f"Last status update: {lu['createdAt'][:10]} ({lu['status']})" if lu else "Last status update: none")

    out += ["", "## Threads on the board", ""]
    by_ws = {}
    for t in a["threads"]:
        by_ws.setdefault(t.get("Workstream") or "(no workstream)", []).append(t)
    for ws in sorted(by_ws):
        out.append(f"### {ws}")
        for t in by_ws[ws]:
            p = t["progress"] or {}
            prog = f"{p.get('completed', 0)}/{p.get('total', 0)}" if p.get("total") else "-"
            out.append(f"- {t['key']} [{t.get('Status') or '-'}] {prog} {t['title'][:70]}")
            out.append(f"  Next: {t.get('Next') or '(empty)'}  · updated {t['updated']}"
                       + (f"  · run {t['run']}" if t["run"] else ""))
        out.append("")

    out.append("## Milestones")
    for m in a["milestones"]:
        out += ["", f"### {m['key']} {m['title']}"]
        for l in m["lines"]:
            refs = ", ".join(f"{r}={s}" for r, s in l["ref_states"].items()) or "no refs: criterion"
            out.append(f"- [{'x' if l['checked'] else ' '}] {l['text'][:90]}  ({refs}){'  ← ' + l['flag'] if l['flag'] else ''}")

    out += ["", "## Orchestrate runs", ""]
    for r in a["runs"]:
        out.append(f"- {r['repo']}#{r['epic']} PR #{r['pr']}: {r['counts']} (state.json {r['modified'][:16]})")
        for k, t in r["live"].items():
            out.append(f"  - {k} {t['status']}: {(t['title'] or '')[:50]}; {(t['note'] or '')[:110]}")

    out += ["", "## Drift", ""]
    labels = {"closed_not_done": "Closed but not Done", "done_but_open": "Done but still open",
              "no_status": "No Status", "no_workstream": "No Workstream",
              "stale_active": "Active but quiet", "tickets_on_board": "Tickets on the board (archive)",
              "epics_off_board": "Open epics not on the board", "milestones_off_board": "Milestones not on the board"}
    for k, label in labels.items():
        if a["drift"][k]:
            out.append(f"- **{label}:** {', '.join(a['drift'][k])}")
    if not any(a["drift"].values()):
        out.append("- none")

    new = [i for i in a["inbox"] if i["new"]]
    out += ["", f"## Inbox: {len(a['inbox'])} open issues not under anything on the board ({len(new)} new since the last update)", ""]
    for i in (new or a["inbox"])[:40]:
        note = f" (parent {i['closed_parent']} closed)" if i["closed_parent"] else ""
        out.append(f"- {i['key']} {i['created']} {i['title'][:80]}{note}")
    if not new and len(a["inbox"]) > 40:
        out.append(f"- … {len(a['inbox']) - 40} more in the snapshot")
    return "\n".join(out)


# ------------------------------------------------------------- apply

def issue_rest(k):
    repo, n = parse_key(k)
    return json.loads(gh("api", f"repos/{OWNER}/{repo}/issues/{n}"))


def apply(changes, dry_run):
    project = fetch_project()
    items = {i["key"]: i for i in project["items"]}
    fields = project["fields"]

    def set_field(item_id, name, value):
        f = fields[name]
        if value in (None, ""):
            q = ("mutation($p:ID!,$i:ID!,$f:ID!){clearProjectV2ItemFieldValue("
                 "input:{projectId:$p,itemId:$i,fieldId:$f}){projectV2Item{id}}}")
            return graphql(q, p=project["id"], i=item_id, f=f["id"])
        if "options" in f:
            opt = {o["name"]: o["id"] for o in f["options"]}
            if value not in opt:
                raise SystemExit(f"{name} has no option {value!r}; options: {sorted(opt)}")
            val = {"singleSelectOptionId": opt[value]}
        else:
            val = {"text": value}
        q = ("mutation($p:ID!,$i:ID!,$f:ID!,$v:ProjectV2FieldValue!){updateProjectV2ItemFieldValue("
             "input:{projectId:$p,itemId:$i,fieldId:$f,value:$v}){projectV2Item{id}}}")
        return graphql(q, p=project["id"], i=item_id, f=f["id"], v=val)

    for c in changes:
        op, k = c["op"], c["key"]
        print(f"{'would ' if dry_run else ''}{op} {k} {json.dumps({x: y for x, y in c.items() if x not in ('op', 'key')})}")
        if dry_run:
            continue
        repo, n = parse_key(k)
        if op == "add":
            q = "mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}"
            item_id = graphql(q, p=project["id"], c=issue_rest(k)["node_id"])["addProjectV2ItemById"]["item"]["id"]
            items[k] = {"item_id": item_id}
            for name, value in c.get("fields", {}).items():
                set_field(item_id, name, value)
        elif op == "set":
            for name, value in c["fields"].items():
                set_field(items[k]["item_id"], name, value)
        elif op == "archive":
            q = "mutation($p:ID!,$i:ID!){archiveProjectV2Item(input:{projectId:$p,itemId:$i}){item{id}}}"
            graphql(q, p=project["id"], i=items[k]["item_id"])
        elif op == "type":
            gh("api", "-X", "PATCH", f"repos/{OWNER}/{repo}/issues/{n}", "-f", f"type={c['type']}")
        elif op == "parent":
            prepo, pn = parse_key(c["parent"])
            args = ["api", f"repos/{OWNER}/{prepo}/issues/{pn}/sub_issues", "-F", f"sub_issue_id={issue_rest(k)['id']}"]
            if c.get("replace"):
                args += ["-F", "replace_parent=true"]
            gh(*args)
        elif op == "blocked_by":
            gh("api", f"repos/{OWNER}/{repo}/issues/{n}/dependencies/blocked_by",
               "-F", f"issue_id={issue_rest(c['blocker'])['id']}")
        elif op == "tick":
            body = issue_rest(k)["body"]
            mark = "x" if c.get("checked", True) else " "
            new, hits = [], 0
            for line in body.splitlines():
                if re.match(r"\s*[-*] \[( |x|X)\] ", line) and c["match"] in line:
                    line = re.sub(r"\[( |x|X)\]", f"[{mark}]", line, count=1)
                    hits += 1
                new.append(line)
            if hits != 1:
                raise SystemExit(f"tick {k}: {c['match']!r} matched {hits} checklist lines, expected 1")
            gh("api", "-X", "PATCH", f"repos/{OWNER}/{repo}/issues/{n}", "-f", "body=" + "\n".join(new) + "\n")
        elif op == "comment":
            gh("issue", "comment", str(n), "-R", f"{OWNER}/{repo}", "--body", c["body"])
        elif op == "close":
            if c.get("comment"):
                gh("issue", "comment", str(n), "-R", f"{OWNER}/{repo}", "--body", c["comment"])
            gh("issue", "close", str(n), "-R", f"{OWNER}/{repo}", "--reason", c.get("reason", "completed"))
        else:
            raise SystemExit(f"unknown op {op!r}")


def set_fields(k, pairs, dry_run=False):
    """`board.py set KEY Field=Value ...`: set fields, adding the item to the board if it is missing."""
    fields = dict(p.split("=", 1) for p in pairs)
    on_board = any(i["key"] == k for i in fetch_project()["items"])
    apply([{"op": "set" if on_board else "add", "key": k, "fields": fields}], dry_run)


RUN_LABELS = [("needs-decision", "needs your decision"), ("fixing", "fixing"), ("reviewing", "in review"),
              ("implementing", "implementing"), ("frontier", "ready"), ("waiting-external", "waiting")]


def sync_run(run_dir, note=None, dry_run=False):
    """Make an orchestrate run's state.json true on GitHub.

    Every ticket the run has merged into its integration branch is closed,
    with a comment naming the merge and the PR. The epic's Next becomes the
    run's progress line, and the epic is added to the board if missing.
    A ticket the final review sends back is reopened by the orchestrator and
    set to `fixing` in state.json, so this never closes it again until it
    re-merges.
    """
    s = json.load(open(os.path.join(run_dir, "state.json")))
    repo = s["repo"].split("/")[-1]
    epic = f"{repo}#{s['epic']}"
    tickets = s.get("tickets", {})

    ops = []
    numbered = {f"{repo}#{k}": t for k, t in tickets.items() if k.isdigit()}
    refs = fetch_refs(numbered)
    for k, t in numbered.items():
        if t.get("status") != "merged" or refs[k] != {"state": "OPEN", "kind": "Issue"}:
            continue
        merge = f" (`{t['merge']}`)" if t.get("merge") else ""
        comment = (f"Merged into `{s['integration_branch']}`{merge} for PR #{s['pr']}. It lands on "
                   f"`{s['base']}` when that PR merges, and is reopened if the final review sends it back.")
        ops.append({"op": "close", "key": k, "reason": "completed", "comment": comment})

    merged = sum(t.get("status") == "merged" for t in tickets.values())
    parts = [f"{merged}/{len(tickets)} merged on PR #{s['pr']}"]
    for status, label in RUN_LABELS:
        ks = [f"#{k}" if k.isdigit() else k for k, t in tickets.items() if t.get("status") == status]
        if ks:
            parts.append(f"{label} {', '.join(ks)}")
    blocked = sum(t.get("status") == "blocked" for t in tickets.values())
    if blocked:
        parts.append(f"{blocked} blocked")
    for n in (s.get("board_note"), note):
        if n:
            parts.append(n)

    item = next((i for i in fetch_project()["items"] if i["key"] == epic), None)
    fields = {"Next": " · ".join(parts)}
    if not item or item["fields"].get("Status") not in ("Active", "Done"):
        fields["Status"] = "Active"
    ops.append({"op": "set" if item else "add", "key": epic, "fields": fields})
    apply(ops, dry_run)
    if not (item or {}).get("fields", {}).get("Workstream"):
        print(f"{epic} has no Workstream: run `board.py set {epic} Workstream=<name>`")


def post_update(status, body):
    pid = fetch_project()["id"]
    q = ("mutation($p:ID!,$s:ProjectV2StatusUpdateStatus!,$b:String!,$d:Date!){createProjectV2StatusUpdate("
         "input:{projectId:$p,status:$s,body:$b,startDate:$d}){statusUpdate{id createdAt}}}")
    r = graphql(q, p=pid, s=status, b=body, d=dt.date.today().isoformat())
    print(r["createProjectV2StatusUpdate"]["statusUpdate"]["createdAt"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--stale-days", type=int, default=14)
    a = sub.add_parser("apply")
    a.add_argument("changes")
    a.add_argument("--dry-run", action="store_true")
    u = sub.add_parser("post-update")
    u.add_argument("--status", required=True,
                   choices=["ON_TRACK", "AT_RISK", "OFF_TRACK", "COMPLETE", "INACTIVE"])
    u.add_argument("--body-file", required=True)
    s = sub.add_parser("set")
    s.add_argument("key")
    s.add_argument("pairs", nargs="+", metavar="Field=Value")
    s.add_argument("--dry-run", action="store_true")
    o = sub.add_parser("sync-run")
    o.add_argument("run_dir")
    o.add_argument("--note", help="appended to the epic's Next, e.g. what an external wait is on")
    o.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.cmd == "report":
        analysis = analyse(fetch_project(), fetch_open_issues(), read_runs(), args.stale_days)
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, "snapshot.json")
        json.dump(analysis, open(path, "w"), indent=1)
        print(render(analysis))
        print(f"\n(snapshot: {path})")
    elif args.cmd == "apply":
        apply(json.load(open(args.changes)), args.dry_run)
    elif args.cmd == "post-update":
        post_update(args.status, open(args.body_file).read())
    elif args.cmd == "set":
        set_fields(args.key, args.pairs, args.dry_run)
    elif args.cmd == "sync-run":
        sync_run(args.run_dir, args.note, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
