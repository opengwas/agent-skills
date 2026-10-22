# OpenGWASDB agent skills

Skills for working on OpenGWASDB with coding agents: Claude Code, pi, Codex, or any harness that reads the open [Agent Skills](https://agentskills.io) format.

| Skill | What it does | Needs |
|---|---|---|
| [`board`](skills/board/SKILL.md) | Syncs the [OpenGWASDB project board](https://github.com/orgs/opengwas/projects/1) with where the work is. It reports each thread against its workstream and milestones, flags drift and unplaced issues, applies the changes you approve, and posts a status update. | `gh`, with the `project` scope |
| [`orchestrate`](skills/orchestrate/SKILL.md) | Runs an epic with parallel worker agents in Herdr panes. Cheap models implement test-first and a stronger model reviews each ticket. One integration branch carries the work, and its draft PR is the dashboard. Store build epics also have explicit acceptance/execution gates and reviewed operational evidence. It keeps the board current as tickets merge. | `board`; Matt Pocock's `tdd`, `code-review` and `resolving-merge-conflicts` in `~/.agents/skills`; [Herdr](https://github.com/herdrdev/herdr); [pi](https://github.com/badlogic/pi-mono); the model accounts listed in the skill |
| [`create-store`](skills/create-store/SKILL.md) | Aligns a Store's shape, sources, filters, ancestry and identity, then files an epic with three dependent tickets: obtain source, create release bundle, run build. Puts the epic in Store builds and hands off to `/orchestrate`. | `gh`; `board`; an `opengwasdb-stores` checkout; optionally Matt Pocock's `grilling` / `/grill-me` for alignment |

All skills run only when you invoke them (`/board`, `/orchestrate`, `/create-store`); none is picked up automatically.

## Install

To use them:

```bash
npx skills add opengwas/agent-skills -g
```

This installs the skills into `~/.agents/skills` and links them for the harnesses you choose. Update with `npx skills update`. Install `board` alongside `orchestrate` and `create-store`: both call its script from the sibling directory.

To change them, clone the repo and link it in:

```bash
git clone https://github.com/opengwas/agent-skills ~/repo/agent-skills
~/repo/agent-skills/install.sh
```

`install.sh` points `~/.agents/skills/<skill>` at the clone, and `~/.claude/skills/<skill>` at that, which is the same layout the skills CLI uses. Edits take effect immediately and are under git. It skips any target that is a real directory rather than a link, so move an older copy aside first.

## Matt Pocock's skills

These skills build on [mattpocock/skills](https://github.com/mattpocock/skills) rather than forking it:
- `orchestrate`'s lanes use `tdd`, `code-review` and `resolving-merge-conflicts`.
- `create-store` can use `grilling` (also exposed as `/grill-me`) to settle ambiguous Store requirements before filing.
- The board's conventions are what `to-spec`, `to-tickets` and `triage` follow.

Install his skills with skills.sh, so that every harness sees them:

```bash
npx skills add mattpocock/skills -g
```

If you only use Claude Code, his plugin works too (`/plugin marketplace add mattpocock/skills`). However, `orchestrate`'s pi lanes read `tdd` and `code-review` from `~/.agents/skills`, so they need the skills.sh install.

## Planning a Store

Invoke `/create-store` in an `opengwasdb-stores` checkout (or supply its path) with
what you want to build. Use “plan only” to get local drafts without GitHub writes.
The skill confirms the Store contract and issue drafts before filing. It then
offers `/orchestrate opengwas/opengwasdb-stores#<epic> — dry run first`.
Filing or orchestrating an epic does not authorise bundle acceptance, costly
execution or publication; those are explicit gates during implementation.

## Where the rules live

The conventions for issues are in the README of the OpenGWASDB project board: workstreams, milestones, epics, tickets as sub-issues, and when a ticket closes. Each repo's agent instructions point there. Change the conventions on the board, not in these skills; `board` reads them on every run.

## Changing a skill

Work in a clone linked with `install.sh` and open a PR. Keep each `SKILL.md` short: put procedure in the skill, and put anything deterministic in its `scripts/`.
