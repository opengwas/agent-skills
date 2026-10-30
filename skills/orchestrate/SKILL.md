---
name: orchestrate
description: "Orchestrate the implementation of a GitHub epic (or any spec broken into tickets with blocking links) with parallel worker agents in Herdr panes: cheap models implement test-first, a stronger model reviews each ticket, and an integration branch with a live draft PR tracks everything until one final review."
disable-model-invocation: true
---

# Orchestrate

You are the **orchestrator**. You don't write the code. You turn an epic into a running
system of parallel workers, make the judgement calls, and keep the user's picture of
progress current. You spend your tokens on decisions, briefs and verification, and the
workers spend theirs on implementation.

`<skill>` below means this skill's directory. Read the repo's `CONTEXT.md` and ADRs first,
if it has them, so your briefs and rulings use the project's vocabulary.

**Store build epics.** For `opengwasdb-stores` work that acquires source data,
creates a Release Bundle or runs Store Release Build (including epics filed by
`/create-store`), read [references/store-builds.md](references/store-builds.md)
before planning, including dry runs. It defines operational evidence and human
gates; code completion alone does not complete these tickets.

## The shape of the run

- **Task graph.** The tickets are a graph with blocking edges, not a list. At any moment
  there is a **frontier** of unblocked tickets; run all of it, up to the lane cap.
- **One integration branch per epic.** Each ticket is built in its own worktree on its own
  branch, cut from the integration branch. After review it merges back with `--no-ff`.
- **A draft PR from minute one.** Open it from the integration branch to the base branch
  as soon as the run starts. Its body is the **dashboard** that the user watches, so update
  it at every state change.
- **One Herdr workspace, one tab per ticket.** Your own tab is renamed
  `orch - <epic name>`. Each ticket gets a tab labelled for it (`#283 freeze`) with two
  panes: the **implementer** on the left and the **reviewer** on the right. A ticket's
  implementer keeps its context across review rounds, so a fix round costs only the delta.
- **Test time is a budget.** A fast suite is what keeps every later lane cheap. Measure it
  at the start, at every merge and at the end. Each review asks whether a ticket's slowdown
  is justified.
- **Files, not chat.** Briefs, reports, notes and state are files in the **run directory**,
  outside the repo. Prompts to workers are one-line pointers to those files.
- **The project board follows the run** in repos that use the `board` skill, as the
  opengwas repos do. A ticket closes when it merges into the integration branch, not when
  the PR lands, so the epic's progress bar moves during the run. The epic's **Next** field
  carries the run's progress line. Both come from `state.json`.

## Run directory and state

Put the run directory at `${CLAUDE_JOB_DIR:-$HOME/.cache/orchestrate}/<repo>-<epic>/`:

```
state.json        source of truth: tickets, statuses, lanes, models, decisions
briefs/<t>.md     what each lane was told       reports/<t>.md   what each lane reported
reviews/<t>-{standards,spec}.md                  notes/            exploration notes
```

Update `state.json` on every transition, then run two commands:
- `python3 <skill>/scripts/dashboard.py <run-dir> --apply` re-renders the PR body.
- `python3 <board>/scripts/board.py sync-run <run-dir>` brings GitHub in line with the state
  (`<board>` is `<skill>/../board`, the `board` skill installed beside this one). It
  closes each newly merged ticket with a comment naming the merge commit and the PR, and
  rewrites the epic's Next on the board.

`sync-run` writes the progress line itself, for example "10/14 merged on PR #299 · fixing
#290 · waiting #289, #291". If something should stay on that line, such as what an
external wait is on, set it as `board_note` in `state.json` rather than passing it once.

State lives in that file, not in your context, because this run will outlive your context. Session
limits, compaction and crashes all happen on long epics. When you resume, the first step is
always to read `state.json` and check `herdr agent list`. If the epic is Paused on the board,
set it back with `board.py set <repo>#<epic> Status=Active`: `sync-run` leaves Paused alone.

Ticket statuses: `blocked`, `frontier`, `implementing`, `reviewing`, `fixing`, `merged`,
`needs-decision`, `waiting-external`.

## Dry run

If the user asks for a plan, preview or dry run, change nothing outside the run directory:
no branches, worktrees, pushes, PRs, issue comments, board updates or Herdr panes. Do steps 1, 2 and 4,
then write to the run directory:
- `plan.md`: the task graph, the frontier, the waiting-external tickets and what releases
  each, a merge order, and per frontier ticket the lane, harness, model, ownership and why;
- `state.json`;
- `briefs/<t>.md` for each frontier ticket;
- `dashboard.md` (`dashboard.py <run-dir>` without `--apply`).

Then stop and show the user `plan.md`. A real run started from that plan reuses those
files.

## Steps

### 1. Read the graph

Fetch the epic and every ticket, including their blocking edges: `gh issue view`,
sub-issues and the "Blocked by" sections. Record each ticket's acceptance criteria and
its blockers. For mixed code/operational work, distinguish implementation from
execution, record the required evidence and approval gates, and release downstream
tickets only when the upstream stage's full criteria are satisfied.

- **External blockers** (another repo's ticket, a data landing, a deploy) put a ticket in
  `waiting-external`. Name exactly what releases it.
- **Prerequisite tickets in sibling repos** that nothing else blocks start immediately, in
  parallel lanes.
- Follow the tracker conventions that the repo's agent instructions point to. For the
  opengwas repos, they are in the project board's README.
- If the epic lists its tickets in a body table instead of as native sub-issues, attach
  them before the run starts, so the board can count them. Use `board.py apply` with
  `parent` ops for the tickets and `blocked_by` ops for their blocking edges. Leave a
  ticket that already has another parent where it is, and tell the user.

### 2. Probe the models

Run `<skill>/scripts/probe_models.sh`. It makes a real one-line call to each candidate and
prints which are live. An auth check alone is not enough: a "ready" credential can still
hold an expired key or an exhausted plan. Record the live chains in `state.json`.

| Role | Chain (first live wins) | Harness |
|---|---|---|
| Implementer | `opencode-go/deepseek-v4.1-flash` → `deepseek/deepseek-flash` → Claude Haiku 5.5 | pi, pi, Claude Code (`claude --model claude-haiku-5-5`) |
| Reviewer | `openai-codex/gpt-6.1-sol` → Claude Opus | pi, then Claude Code, in the ticket's reviewer pane |
| Escalation implementer | Claude Sonnet or Opus | Claude Code, in the ticket's implementer pane |

Haiku runs through Claude Code rather than pi, because pi's Anthropic route bills
third-party usage separately.

Re-probe when a lane dies with an auth, quota or credit error. Mark that model dead in
`state.json` and restart the lane on the next live model. The lane's worktree and commits
survive the switch.

### 3. Open the integration branch and draft PR

1. Cut `orch/<epic>-<slug>` from the base branch. Take the base branch from CONTRIBUTING
   or the user, not from an assumption that it is `main`.
2. Make an empty kickoff commit (`git commit --allow-empty -m "Start orchestration of #<epic>"`),
   because a branch with no commits cannot open a PR.
3. Push, then `gh pr create --draft` with the dashboard body.
4. Record the PR number in `state.json`, then run `board.py sync-run <run-dir>`. That puts
   the epic on the board as Active, with the run's progress as its Next. If the epic has
   no Workstream yet, set one with `board.py set <repo>#<epic> Workstream=<name>`. Ask the
   user if the right workstream isn't obvious.

Tickets close as they merge into the integration branch (step 9), so the PR body needs no
closing keywords for them. Keywords fire only when the base is the default branch. With
base `main`, `Closes #<epic>` closes the epic when the owner merges; on any other base it
wouldn't fire, and the owner closes the epic.

5. Run `lane.py init <run-dir> "<epic name>"` to rename your tab.
6. Start the **test-time baseline**: the full suite on the kickoff commit, in a detached
   worktree with its own environment, in the background. Record wall time and per-suite
   times in `state.json` under `test_time.baseline`. Every later comparison is against
   this.

### 4. Plan the frontier before launching it

Running lanes in parallel only pays off if they don't collide at merge time. For the
frontier:

- **Ownership.** Run one exploration subagent (cheap model) to list the files and regions
  each ticket will touch. It writes `notes/<t>.md` so workers don't each re-explore.
- **Assign ownership in the briefs.** For example: "you own `freeze.py` and the new
  modules; #284 owns lines 1010–1835 of `candidate_workflow.py`; stay out".
- **Schedule real conflicts.** Where two tickets must edit the same region, serialise them,
  or have the later one merge the earlier one's branch and resolve. Decide the merge order
  now.
- **Seams.** The `tdd` skill tests only at agreed seams. Derive each ticket's seams from
  its acceptance criteria, write them into the brief, and list them on the dashboard so the
  user can object. Treat silence as agreement, and don't ask per ticket.

### 5. Brief and launch lanes

Per ticket:

1. **Worktree.** `git worktree add <worktrees>/<t> -b orch/<epic>/<t> <integration-branch>`.
   Never work in the user's primary checkout: other sessions may be switching branches in it.
2. **Brief.** Write `briefs/<t>.md` from [references/brief-template.md](references/brief-template.md). Point at the
   ticket, the ADRs and the notes rather than restating them. Spell out:
   - worktree, branch and environment setup;
   - lane ownership;
   - seams;
   - stop-and-report gates;
   - the commit trailer;
   - in a repo with `changelog.d/`, the ticket's changelog fragment, per CONTRIBUTING;
   - "don't push";
   - the report path and format.
3. **Model.** Default to the implementer chain. Escalate to Claude Code (Sonnet, or Opus
   for the hardest) in the same pane when:
   - the ticket designs a contract, schema or cross-cutting refactor;
   - a flash lane has failed twice;
   - the work needs judgement on real data rather than following a precise spec.

   Escalating costs more per ticket but less than two failed rounds.
4. **Launch.** `lane.py start <run-dir> <t> "<tab label>" <harness> <model> <worktree> <brief>`
   creates the ticket's tab and both panes, starts the implementer, and sends the one-line
   pointer prompt. Run it with `run_in_background` so you are notified when the lane
   settles, instead of polling. [references/herdr-lanes.md](references/herdr-lanes.md)
   has the commands and the diagnosis table.

Cap concurrent heavy lanes (default 4). Past that, rate limits and session limits cost
more time than the parallelism saves.

While lanes run, prepare the next briefs, and check pairwise conflicts between running
branches (`git merge-tree --write-tree --name-only A B`). Don't read lane transcripts or
pane scrollback; it is the most expensive way to learn little.

### 6. When a lane settles

1. Read `reports/<t>.md`.
   - **No report:** the lane died. `lane.py` prints the likely cause: an auth or credit
     error, a session limit, a blocked UI. Then resume, switch model, or re-brief.
   - **`blocked`:** the agent hit a question or approval UI. Look at it before answering
     anything.
2. **Verify claims cheaply.** Run `git log` and `git diff --stat` against the integration
   branch, and confirm the test-log path the report cites exists and says what the report
   says. Check that protected paths are untouched.

   Check the report's test timings, base against head, for the affected suites.

   Workers misreport. One counted test suites from a notification it never checked.
   Cheap models also leak brief phrasing into docs ("measure it, do not claim it") and
   mangle commit trailers. Read the diff's prose and trailers.
3. If the worker stopped at a gate, see step 8.

### 7. Review each ticket before it merges

Run a two-axis review: **Standards** and **Spec**, as defined by the `code-review` skill.

- **Fixed point:** the integration branch.
- **Reviewers:**
  - Write both briefs from [references/review-briefs.md](references/review-briefs.md).
  - Run `lane.py review <run-dir> <t> <harness> <model> <standards brief> <spec brief>` in
    the background. Both axes run in parallel in the ticket's reviewer pane, as separate
    read-only processes. They write `reviews/<t>-standards.md` and `reviews/<t>-spec.md`.
  - Use the first live model of the reviewer chain.
- **Test cost** is part of the Standards axis. The reviewer compares the implementer's
  base-against-head suite timings and flags growth past the thresholds in the brief. Some
  growth is justified, such as a new real-data guard. Then the question is whether it is
  needed on every run, or belongs behind a marker or in a slower tier.
- **Rule on the findings.** You are the judge, not a relay. For each finding, decide fix,
  accept or reject, and settle the design questions it raises (state the choice and the
  reason).
- **Send fixes.** Write a numbered fix list and send it to the **same lane**, with
  `lane.py prompt`.
- **Re-review after fixes** only when the fixes changed behaviour. Otherwise re-verify
  cheaply as in step 6.

Review every ticket, small ones included. In practice it finds a real defect in most
tickets: a cache that re-resolves on a revisit, a guard that runs before normalisation, a
silent default.

### 8. Decisions

Workers hit spec gaps. A good brief tells them to stop and report rather than guess.

- **Decide yourself** anything a sensible default, the ADRs or the code can settle. Say
  what you decided and why, in the fix list and in the dashboard's decision log.
- **Ask the user** (AskUserQuestion) only for real product or scientific choices,
  especially ones that change acceptance criteria or published data. Present options with
  counts and examples taken from the worker's measurement, and a recommendation.
- **Record every decision** on the ticket as a comment, and in an ADR clarification note if
  it refines a decision record. Do this at the moment of decision, not at the end.

### 9. Merge into the integration branch

1. The lane merges the integration tip into its branch and re-runs the affected suites
   before reporting done. The brief says so.
2. Merge the ticket branch into the integration branch with `--no-ff`.
3. Run a fast smoke test (the affected suites) in a detached worktree. Record its time
   next to the baseline's for the same suites. Push.
4. Set the ticket to `merged` in `state.json` (its `merge` is the bare merge commit hash,
   which `epic_record.py` reads), then re-render the dashboard and run `board.py sync-run`. That closes the ticket with a comment naming the merge commit and
   the PR, and moves the epic's Next.
5. If the merge conflicts, give it to a merger lane with the `resolving-merge-conflicts`
   skill. Resolve by intent, keeping both behaviours, not by picking a side.

Re-compute the frontier and launch whatever it opened.

### 10. Finish

1. Run the full test suite once, on the integration branch, in a detached worktree with
   its own environment. Compare its wall time and its slowest suites with
   `test_time.baseline`, and put the comparison on the dashboard. Explain any growth past
   10% ticket by ticket, or fix it before marking the PR ready.
2. Review the whole integration branch against the base branch. Use the same two
   briefs, with the fixed point set to the base branch, run in a `final` ticket tab. Fix
   the findings in one lane.

   If a finding sends a merged ticket's work back:
   - reopen the ticket with `gh issue reopen <n> --comment "<why>"`;
   - set its status to `fixing` in `state.json`.

   `sync-run` closes it again when it re-merges.
3. **Project site.** Only if the repo has `docs/spec/project-site.md`; otherwise skip to 4.
   [references/project-site.md](references/project-site.md) has the rules.
   - Run `pixi run yardstick` on the integration branch if the reference's window and a quiet
     host allow, and commit the result. Otherwise defer it, and say so in `board_note`.
   - Set the record's optional keys in `state.json` (`workstream`, `yardstick`, and `catalog`
     if the epic changes Store data), as the reference says.
   - Write the summary (2–4 sentences) to `<run-dir>/notes/summary.md`, then run
     `python3 <skill>/scripts/epic_record.py <run-dir> --summary-file <run-dir>/notes/summary.md
     --out docs/_epics/<repo>-<n>.yaml` on the integration branch. Validate it with the
     repo's validator, fix what it names, and commit it. Rerun it when a deferred yardstick lands.
   - Version notes for the epic PR are the lanes' changelog fragments.
4. Mark the draft PR ready, and render the final dashboard. It lists tickets, decisions,
   follow-up issues filed, and anything left in `waiting-external`. Set `board_note` to
   "ready for your review" and run `sync-run` once more.
5. Don't merge the PR into the base branch. That review is the user's.
6. Clean up the worktrees, and the Herdr tabs and panes this run created, and nothing else.

## Guardrails that save the most time

- **Commit often.** Every brief says to commit after each green slice, by explicit path,
  never `git add -A`. A lane that dies at a session limit then loses minutes, not hours.
- **Spec and code land in one commit.** If a contract changes, its spec is in the same
  commit, and every commit imports and passes on its own. Ask the lane to squash into
  coherent commits before it reports.
- **Make tests that can fail.**
  - New tests are observed failing first.
  - Expected values come from an independent source. A strong pattern: pin literals by
    running the *base-branch* code from an archive, never the new code.
  - Where tests already pass, prove they can fail with a deliberate mutation.
- **Real data where it matters.** If a ticket regenerates something already published,
  "byte-identical, or every difference explained" is the acceptance test. Run it as a
  verification step, not as a unit test.
- **Nothing outward without the user.** You push branches, comment on tickets, and close
  tickets as they merge into the integration branch, reopening any the final review sends
  back. You also keep the epic's board fields current. You don't
  merge to the base branch or delete remote branches. Publishing is also off-limits
  except for a Store build operation whose command, host, budget and publication
  effect the user explicitly approved under [the Store build gates](references/store-builds.md).
  If a permission prompt blocks an action, stop and tell the user why it's needed.
- **Report in a fixed shape** (see [references/brief-template.md](references/brief-template.md)): results with evidence,
  commits, decisions taken, decisions needed. Keep it to about 400 words. Reports that
  ramble cost your context on every lane.
