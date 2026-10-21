---
name: board
description: "Sync the OpenGWASDB project board with where the work actually is: report each thread against its workstream and milestones, flag drift and unplaced issues, apply the changes the user approves, and post a dated status update."
disable-model-invocation: true
---

# Board

The [OpenGWASDB project board](https://github.com/orgs/opengwas/projects/1) is the single record of where work stands. Its README defines the model:
- workstreams;
- milestones that list the epics they need;
- epics on the board;
- tickets as sub-issues, kept off the board.

It also holds the conventions other skills follow. Read it at the start of every run:

```bash
gh project view 1 --owner opengwas --format json --jq .readme
```

This skill measures the board against that README and against reality. It proposes a changeset and applies only what the user approves. It keeps no state of its own. The record is:
- the board itself;
- the issues;
- orchestrate's `state.json` files;
- the project's status updates.

`<skill>` below means this skill's directory.

## Modes

- **`/board`**: a sync. The inbox covers issues created since the last status update.
- **`/board status`**: steps 1 and 2, then a summary. Change nothing.
- **`/board reset`**: a sync whose inbox covers every unplaced issue. Use it after a long gap.

## Steps

### 1. Measure

Run `python3 <skill>/scripts/board.py report`. It prints:
- the threads on the board, by workstream;
- each milestone's checklist, with the state of every issue the checklist names;
- the orchestrate runs;
- drift;
- the inbox: open issues with no open ancestor on the board.

It also caches the full snapshot at `~/.cache/board/snapshot.json`.

### 2. Understand each Active thread

An epic with an orchestrate run is kept current by the orchestrator: each transition runs `board.py sync-run <run-dir>`, which closes merged tickets and rewrites the epic's Next. Run `sync-run` for every run in the report, then check that the run still looks alive. If its `state.json` is days old while tickets are in flight, flag the run as stalled.

For every other Active epic, decide what its **Next** line should now say: one sentence about what happens next, or what it waits on. Sources, cheapest first:
1. The epic's sub-issue progress and its latest comments (`gh issue view <n> -R opengwas/<repo> --comments`).
2. Recently merged PRs that reference it.

Look for links between threads. For example, a ticket in one epic may wait on another epic's work, or two orchestrate runs may be editing the same code. Neither run can see the other, so these go in Next and in the status update.

Don't read lane transcripts or diffs.

### 3. Draft the changeset

Work through the report and propose changes.

- **Fields.**
  - Write a Next line for each Active thread.
  - Change Status where it's wrong. An Active thread that has been quiet past the stale window becomes Paused unless something says otherwise; a closed one becomes Done.
  - Fill in any missing Workstream.
- **Milestones.**
  - Tick or untick checklist lines.
  - The script's `tick?` and `untick?` flags are only hints. A line can name an issue that stays open after its criterion is met (for example "#282 stage 1 merged"), so judge each line by its text.
  - A criterion line with no reference needs evidence before you tick it.
  - An MVP that no issue delivers is a gap. Propose an issue for it, or flag it as a decision.
- **Epics not on the board.** Either add them with Workstream and Status, or propose closing them as superseded and name what superseded them.
- **Finished epics.** An epic whose sub-issues are all closed, and whose integration PR (if any) has merged into `dev`, gets closed and set to Done. If the PR hasn't merged, the epic is waiting on the user's review. Say so in Next.
- **Tickets on the board.** Archive them.
- **Ticket tables.** An epic that lists its tickets in a body table gets them attached as sub-issues (`parent` ops). Skip any ticket that already has a parent, unless the user agrees to move it.
- **Inbox.** For each unplaced issue, propose one of:
  - make it a sub-issue of an existing epic;
  - use it as the seed of a new epic (draft a title and pick a workstream);
  - put it on the board as a standalone item;
  - leave it.

  Group related issues: three new issues about one subsystem are usually one new epic. In `/board reset`, the inbox is large. Have a subagent read the titles and bodies and return a table, then review that table yourself before showing it.

### 4. Ask, then apply

Show the changeset as tables grouped by kind, and give the reason for anything non-obvious. Show the draft status update from step 5 alongside it. Ask the user to approve, edit or drop items. Closing an issue, creating one, and moving an issue to a different parent each need explicit approval.

Write the approved changes to `~/.cache/board/changes-<date>.json`. Run `board.py apply <file> --dry-run`, then run it again without `--dry-run`. The ops are:

```json
[
  {"op": "add", "key": "opengwasdb-stores#313", "fields": {"Status": "Active", "Workstream": "Interface", "Next": "…"}},
  {"op": "set", "key": "opengwasdb-stores#282", "fields": {"Next": "…", "Status": "Paused"}},
  {"op": "archive", "key": "opengwasdb#53"},
  {"op": "type", "key": "opengwasdb-stores#282", "type": "Epic"},
  {"op": "parent", "key": "opengwasdb-stores#283", "parent": "opengwasdb-stores#282"},
  {"op": "blocked_by", "key": "opengwasdb-stores#289", "blocker": "opengwasdb-stores#222"},
  {"op": "tick", "key": "opengwasdb#292", "match": "opengwasdb-stores#314", "checked": true},
  {"op": "comment", "key": "opengwasdb-stores#176", "body": "…"},
  {"op": "close", "key": "opengwasdb-stores#216", "reason": "not planned", "comment": "…"}
]
```

- A key is `<repo>#<number>` within the opengwas org.
- A field value of `""` clears that field.
- `tick` needs `match` to hit exactly one checklist line.
- `parent` takes `"replace": true` to move a ticket that already has a parent.

### 5. Post the status update

Draft a short update covering:
- **Moved since the last update** (the report gives its date): the epics and milestone lines that advanced.
- **Next:** the two or three things that matter most, across all threads.
- **Decisions needed** from the user.
- **Milestones:** one line each, with lines met out of total and what's left.

Give an issue its title the first time you mention it.

Choose the status from the first open milestone:
- `ON_TRACK`;
- `AT_RISK`, if something on its list is blocked or quiet;
- `OFF_TRACK`.

Once the user approves, post it with `board.py post-update --status <S> --body-file <file>`.

## Guardrails

- **The board README is the rulebook.** If reality keeps contradicting it, for example work that fits no workstream, raise that with the user instead of working around it.
- **Nothing changes without approval.** `/board status` changes nothing.
- **Keep it light.** A sync takes minutes. Don't re-plan epics: surface what needs a decision and move on.
- **Tickets keep appearing on the board?** The project's "Auto-add sub-issues to project" workflow has been switched on. It should be off. Tell the user, because only the web UI can change it.
