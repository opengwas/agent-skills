# Running lanes in Herdr

`scripts/lane.py` wraps every Herdr call a lane needs. Read this before the first launch
and again when a lane misbehaves. For anything the script doesn't cover, the `herdr`
skill and `herdr --help` are the authority.

**Precondition:** the orchestrator runs inside a Herdr pane (`HERDR_ENV=1`). If it
doesn't, say so and stop. Don't drive the user's focused session from outside.

## Layout: one workspace, one tab per ticket

```
workspace (the orchestrator's own)
├── tab "orch - <epic name>"   ← this session, renamed by `lane.py init`
├── tab "#283 freeze"          ← one per ticket: [ implementer │ reviewer ]
├── tab "#284 resolution"
└── …
```

Use labels like `#<issue> <two-word slug>`, or `T1 suite rename` when tickets live in a
file. The user switches tabs to watch a ticket.
- **Left pane, the implementer.** One interactive agent. It keeps its context across fix rounds.
- **Right pane, the reviewer.** Each review round runs both axes, Standards and Spec, as
  parallel one-shot processes. They don't share context, which keeps the two axes
  independent, as `code-review` intends.

```bash
python3 <skill>/scripts/lane.py init <run-dir> "<epic name>"
```

## Implementer

Run each `start` with `run_in_background`. It returns when the lane settles.

```bash
# Default chain: pi.
python3 <skill>/scripts/lane.py start <run-dir> 283 "#283 freeze" pi deepseek/deepseek-flash <worktree> <run-dir>/briefs/283.md
# Haiku fallback, or Claude escalation (sonnet or opus): Claude Code in the same left pane.
python3 <skill>/scripts/lane.py start <run-dir> 283 "#283 freeze" claude claude-haiku-5-5 <worktree> <run-dir>/briefs/283.md
```

`start` takes five steps:
1. It creates the ticket's tab with both panes.
2. It labels the panes `impl · <model>` and `review`.
3. It starts the agent. pi gets `--thinking high --skill ~/.agents/skills/tdd`; Claude Code
   uses `ORCH_CLAUDE_PERMISSION_MODE`, default `auto`.
4. It sends a one-line pointer to the brief.
5. It waits, then prints:

```
LANE 283 implementer settled: status=done report=present (<run-dir>/reports/283.md)
```

If the report is missing or the lane is blocked, it also prints up to five `SUSPECT` lines
(auth, quota or credit errors; rate or session limits).

Send fix rounds to the same agent:

```bash
python3 <skill>/scripts/lane.py prompt <run-dir> 283 <run-dir>/briefs/283-fix1.md
```

An implementer that runs outside Herdr, such as an in-session Claude agent started before
the run, still gets a ticket tab, so its review runs in the same place as every other:

```bash
python3 <skill>/scripts/lane.py adopt <run-dir> 287 "#287 release config" <worktree>
```

## Reviewer

Run in the background:

```bash
python3 <skill>/scripts/lane.py review <run-dir> 283 pi openai-codex/gpt-6.1-sol \
    <run-dir>/briefs/283-review-standards.md <run-dir>/briefs/283-review-spec.md
```

Fallback, when gpt-6.1-sol is not live:

```bash
python3 <skill>/scripts/lane.py review <run-dir> 283 claude opus <standards brief> <spec brief>
```

`review` writes a round script to `reviews/283-round<k>.sh` and runs it in the right pane.
It waits for the round's marker and prints:

```
REVIEW 283 round 1 settled: standards=present, spec=present
```

Each axis's raw output is kept in `reviews/283-<axis>-round<k>.log`.

## Diagnose

```bash
python3 <skill>/scripts/lane.py status <run-dir>                 # every ticket: tab, implementer state, review rounds
python3 <skill>/scripts/lane.py tail <run-dir> 283 impl 120      # implementer pane text, only to diagnose
python3 <skill>/scripts/lane.py tail <run-dir> 283 review 60     # reviewer pane
```

| Symptom | Meaning | Do |
|---|---|---|
| `report=MISSING` with a `SUSPECT` auth, 401/402, credit or quota line | the model is out of credit, or its key is dead | Mark the model dead in `state.json` and re-probe. `stop` the ticket's tab, then `start` again on the next live model with the same worktree. Commits survive. |
| `report=MISSING` with a 429, rate-limit or overloaded line | transient | Wait a few minutes, then `prompt`: "continue; commit what you have first". |
| session or usage limit (Claude) | the account limit was hit | Record the reset time in `state.json` and resume after it. |
| `TRUST <ticket>` at start (Claude Code) | Claude Code asks whether to trust a directory it hasn't seen; every new worktree path does this | Ask the user **once per run** whether to trust this run's worktrees, then run the printed `send-keys` + `prompt`. Never accept trust for a directory outside the run's worktrees. |
| `status=blocked` | an approval or question UI | `tail` it. Answer only what you would decide yourself; otherwise ask the user. |
| `status=done` and a report, but `git log` is empty | the worker described work it didn't commit | Re-prompt with the commit rule. Don't accept the report. |
| `REVIEW … MISSING` | a reviewer process failed | Read `reviews/<t>-<axis>-round<k>.log`, then retry the round or fall back to the next reviewer. |
| implementer `gone` | the agent exited | `stop` the tab, then `start` again on the same worktree with a resume brief ("read your report and git log, then continue"). |

## Cleanup

```bash
python3 <skill>/scripts/lane.py stop <run-dir> 283     # the ticket's tab, once its branch has merged
python3 <skill>/scripts/lane.py cleanup <run-dir>      # every ticket tab this run created
```

Never close tabs the run didn't create. Leave the orchestrator's tab as it is.
