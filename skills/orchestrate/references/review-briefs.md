# Reviewer briefs

These two briefs carry the `code-review` skill's two axes. `lane.py review` runs them in
parallel, as separate one-shot processes in the ticket's reviewer pane. Use whichever
reviewer the chain gives you: `openai-codex/gpt-6.1-sol` on pi, or Claude Opus on Claude
Code. The briefs are the same for both.

The axes stay separate on purpose. Code can follow every standard and still build the
wrong thing, or build the right thing in breach of the standards. One reviewer doing both
lets one finding mask the other.

Write each brief to `briefs/<n>-review-{standards,spec}.md`.

## Standards reviewer

```markdown
# Standards review of #<n>. Read-only: don't edit, commit or push anything.

Work in `<worktree>`.
- Diff: `git diff <integration>...HEAD` (three-dot, against the merge-base).
- Commits: `git log <integration>..HEAD --oneline`.

Standards sources:
- `CONTRIBUTING.md`, plus `CLAUDE.md` or `AGENTS.md` if present;
- `CONTEXT.md` (its vocabulary and its _Avoid_ lists);
- the ADRs the diff touches or cites.

Also apply the smell baseline in `~/.agents/skills/code-review/SKILL.md` (section 3). Every smell is a labelled judgement call, and a documented repo standard overrides it.

Look hard at:
<the orchestrator's specific worries for this ticket, e.g. a lock's scope, a silent default, duplicated helpers, test independence>

**Test cost.** Efficient tests are a standard here.
- The implementer's report gives base and head timings for the affected suites, and the
  full-suite wall time: `<run-dir>/reports/<n>.md`.
- Check them against the logs it cites. Flag any suite more than 20% or 30 s slower, and any
  new test slower than 5 s.
- For each flagged item, judge whether the cost is needed on every run. If it isn't, name
  the fix: a smaller fixture, shared or session-scoped setup, a slow marker or tier, or
  mocking an expensive boundary that isn't under test.
- Flag a missing timing as a finding in itself.

Report to `<run-dir>/reviews/<n>-standards.md`, at most 400 words, then reply with only that path.
- (a) Each violation of a documented standard: cite the file and the rule, and quote the hunk.
- (b) Each baseline smell: name it and quote the hunk.
Mark each finding as a hard violation or a judgement call. Skip anything the repo's tooling already enforces.
```

## Spec reviewer

```markdown
# Spec review of #<n>. Read-only: don't edit, commit or push anything.

Work in `<worktree>`.
- Diff: `git diff <integration>...HEAD`.
- Commits: `git log <integration>..HEAD --oneline`.

Spec sources:
- `gh issue view <n> --comments`. Comments may amend the acceptance criteria; the latest decision wins.
- <ADR paths and the lines that bind this ticket>.
- The orchestrator's brief at `<run-dir>/briefs/<n>.md` (scope, ownership, seams).

The implementer made these decisions; judge each one against the spec:
<numbered list from the implementer's report>

Verify claims against the code, not the commit messages:
<specific checks, e.g. "re-run the regeneration diff with your own rewrite, not the implementer's function", "check that X is refused">

Report to `<run-dir>/reviews/<n>-spec.md`, at most 400 words, then reply with only that path.
- (a) Requirements missing or only partly done.
- (b) Behaviour nobody asked for (scope creep).
- (c) Requirements that look implemented but are wrong.
Quote the spec line for each finding.
```

## Ruling on the findings

You are the judge. For each finding, decide fix, accept with a reason, or reject with a
reason. Then write the fix list.

Give extra weight to these findings, because they recur:
- silent defaults or fallbacks in place of a loud failure;
- tests that can't fail: tautological expectations, or fixtures that never reach the code path;
- a cache, resume or reuse path that recomputes or diverges on revisit;
- guards applied before normalisation, not after;
- contract changes landing without their spec;
- vocabulary the glossary says to avoid;
- test time that grew without a reason. Accept growth only when the test can't be cheaper
  and must run every time; otherwise send the cheaper form as a fix.
