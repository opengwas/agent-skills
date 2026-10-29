---
name: create-store
description: "Set up an OpenGWASDB Store Release: align its scientific and operational requirements, then file an epic with obtain-source, create-release-bundle and run-build tickets in the Store builds workstream."
disable-model-invocation: true
---

# Create store

Turn a Store request into an implementation-ready epic in `opengwas/opengwasdb-stores`.
This skill plans and files the work; `/orchestrate` implements it. Filing the epic
is not permission to acquire restricted data, accept a Release Bundle or publish a Store.

`<skill>` means this directory; `<repo>` means the user's `opengwasdb-stores`
checkout. `<board>` is the sibling `../board` skill directory.

## 1. Discover the constraints

Read `<repo>/AGENTS.md`, `CONTRIBUTING.md`, `CONTEXT.md` and the board README:

```bash
gh project view 1 --owner opengwas --format json --jq .readme
```

Read the repository's current `docs/spec/source-connectors.md`,
`docs/spec/release-config.md`, `docs/spec/store-release-workflow.md` and the ADRs
those documents cite for the proposed choices. Use the current contracts, CLI
help and comparable releases rather than copying an old bundle's schema.

Search open epics in **both** OpenGWASDB repos, their sub-issues, registered
releases, generator configs and active worktrees/runs for overlapping work and
reserved Store ids. Reuse suitable acquisition, inventories, connectors and
Reference Resources. Ask before extending an existing epic or moving a ticket
from another parent. Missing readers, resolver support or Reference Resources
are explicit prerequisite issues, not statistics to implement in the registry.

Done when you can name the reusable assets, overlaps and capability gaps, with
paths or issue links. If GitHub is unavailable, draft locally and report that
filing and duplicate checks remain incomplete.

## 2. Align the Store contract

Work through [references/store-contract.md](references/store-contract.md).
Fill facts from the repository and source evidence yourself; ask the user only
for scientific, product and operational decisions. Show recommendations with
the evidence and trade-offs.

**Grill when needed.** If choices conflict, important requirements are unclear,
or the user asks to stress-test the plan, offer `/grill-me` and carry this
contract into that interview. It is a user-invoked alias for `grilling`; where
the model-invoked `grilling` skill is available, use it directly. Otherwise run
the same decision-tree interview here: ask the current frontier of independent
questions with recommendations, wait, then ask the decisions they unlock.
Resume this skill with the settled answers; a separate interview is unnecessary
when the user already supplied a complete, consistent contract.

Record each contract item as **agreed** (value, evidence/decision), **not
applicable** (reason), or **blocked** (named prerequisite, owner and release
condition). A worker may measure an unknown count later; its expected bounds
and what happens on disagreement must be agreed now. A scientific choice with
no agreed decision or named resolution gate keeps the draft local.

Show the completed contract and obtain explicit confirmation of shared
understanding before filing. One Store Release has one Selection from one
homogeneous Source Collection. If the request requires several releases, agree
the split and create a separate three-ticket epic per release, sharing upstream
prerequisites where appropriate.

## 3. Draft the epic and three tickets

Use [references/tickets.md](references/tickets.md). Create exactly these three
stage tickets under the epic, in order:

1. **Obtain source** — reproducible acquisition/reuse, source metadata, identity
   mapping and integrity evidence.
2. **Create release bundle** — freeze, resolve, select, emit and human acceptance.
3. **Run build** — resource/runtime preflight, approved execution and validation.

The native dependency chain is `Obtain source → Create release bundle → Run
build`. Put a **Blocked by** section in each ticket too, for readers and
`orchestrate`; external blockers name their release conditions. A prerequisite
in `opengwasdb` or another epic is linked, not silently added as a fourth stage.
Already available source still has an obtain-source ticket: verify its identity
and provenance instead of downloading again.

The epic holds the authoritative agreed contract, non-goals, decision gates and
completion criteria; tickets link to it and specify stage evidence. Include
`## Store build orchestration` in the epic, linking the three-stage workflow
and naming who can accept the bundle, approve execution and review evidence.
A ticket is complete only when its stage evidence is reviewed and committed;
implementation of a downloader or successful process exit alone is insufficient.

Show all four issue drafts, existing issues to reuse, prerequisite links and
the proposed board changes. Ask for approval to create/update them. In **plan
only / dry run**, write drafts and proposed operations locally and stop: no
GitHub writes, acquisition, generation, builds, branches or worker launches.

## 4. File and verify

After approval, use `gh issue create -R opengwas/opengwasdb-stores --title …
--body-file …` for the epic and each missing stage ticket. Capture every returned
URL immediately in a local filing receipt. Before resuming a partial run, fetch
the recorded issues and search for any unrecorded successful creation; create
only missing pieces. Never blindly repeat creation after a timeout.

Use `python3 <board>/scripts/board.py apply <ops.json> --dry-run`, inspect it,
then apply without `--dry-run`. The approved ops must:

- set the epic's issue type to `Epic`;
- add the epic to project 1 with `Workstream=Store builds`, `Status=Todo`, and a
  concrete `Next` (first action or named blocker); preserve an existing epic's
  live Status when extending it;
- attach the three stage tickets as native sub-issues using `parent` ops;
- create the chain and external dependencies with `blocked_by` ops.

For example (substitute the created issue numbers):

```json
[
  {"op":"type","key":"opengwasdb-stores#1000","type":"Epic"},
  {"op":"add","key":"opengwasdb-stores#1000","fields":{"Workstream":"Store builds","Status":"Todo","Next":"Verify source acquisition for the agreed Selection"}},
  {"op":"parent","key":"opengwasdb-stores#1001","parent":"opengwasdb-stores#1000"},
  {"op":"parent","key":"opengwasdb-stores#1002","parent":"opengwasdb-stores#1000"},
  {"op":"parent","key":"opengwasdb-stores#1003","parent":"opengwasdb-stores#1000"},
  {"op":"blocked_by","key":"opengwasdb-stores#1002","blocker":"opengwasdb-stores#1001"},
  {"op":"blocked_by","key":"opengwasdb-stores#1003","blocker":"opengwasdb-stores#1002"}
]
```

Check existing types, parents, dependencies and project fields before applying
a repair; omit operations already satisfied. Update the tickets' textual
**Blocked by** sections with the real issue links. Follow the board README for
any agreed milestone linkage; never add stage tickets to the board or list them
in an epic-body ticket table.

Re-fetch the epic type, native sub-issues, dependencies and project fields
(`gh api` and `gh project item-list`, with pagination as needed). Done means all
three tickets have the intended parent, both chain edges exist, and only the
epic is on the board in **Store builds** with the agreed fields. Report any
partial filing or permission failure with the existing URLs and remaining ops;
a printed apply command is not verification.

## 5. Hand off

Return the epic URL, the three ticket URLs, named blockers and next gate. Offer:

```text
/orchestrate opengwas/opengwasdb-stores#<epic> — dry run first; checkout <repo>; base <the branch CONTRIBUTING names>
```

Use the repository's actual base branch. The
orchestrator reads its `references/store-builds.md` for these mixed code and
operational tickets. Stop here unless the user explicitly asks to start that
separate run; approvals for acceptance, costly execution and publication remain
separate from permission to orchestrate.
