# Implementer brief template

Write one brief per ticket to `briefs/<ticket>.md`. Fill every `<…>`. Delete any section
that doesn't apply rather than leaving it empty.

A brief is **pointers plus the things only you know**: ownership, seams, gates and
decisions already taken. The worker reads the ticket, ADRs and notes itself, so don't
paste them in.

```markdown
# Ticket #<n>: <title>

You are implementing <repo> issue #<n>, part of epic #<epic>.

## Read first
- `gh issue view <n> --comments` (the comments may carry decisions and findings from earlier tickets)
- <ADR paths>, `CONTEXT.md` (use its vocabulary; avoid its _Avoid_ terms in new lines)
- `CONTRIBUTING.md` (its standards are binding)
- `<run-dir>/notes/<n>.md` (exploration notes: the files and regions this ticket touches)

## Where you work
- Worktree `<path>`, branch `<branch>`, cut from the integration branch `<integration>` at `<sha>`.
  Work only here. Never touch `<primary checkout>` or other worktrees.
- Environment: `<setup command, e.g. pixi install --locked -e dev>`, then run everything from inside the worktree.
- Stage explicit paths only; never `git add -A`.
- Commit after every green slice. Commit messages end with `(#<n>)` and the trailer:
  `<Co-Authored-By trailer>`.
- If the repo has `changelog.d/`, add the ticket's fragment, as CONTRIBUTING says. The epic PR's version notes are those fragments.
- If a contract or schema changes, its spec goes in the same commit. Every commit must import and pass on its own.
- Don't push. Don't open PRs.

## Lane ownership (parallel lanes are running)
- You own: <files / regions / new modules>.
- Stay out of: <files / regions owned by #x, #y>. If you must touch them, keep it minimal and additive, and say so in your report.

## What to build
<Two to six lines naming the deliverable in the ticket's own terms. Pointers, not a restatement.>
<Decisions already taken that the ticket doesn't record, with their reasons.>

## TDD: pre-agreed seams
Use the `tdd` skill. Test only at these seams; write each test first and watch it fail:
1. <seam: public interface + behaviour>
2. <…>
Expected values come from an independent source: a literal, a worked example, or the
base-branch code run from an archive. Never recompute them the way the new code does.

## Stop and report instead of guessing
Stop, commit what you have, and report if:
- <a spec gap you can foresee, e.g. "normalising would change a published bundle's values">
- the work needs a change in <other repo / shared contract> beyond what this brief allows
- a needed decision isn't covered by the ticket, its comments, or this brief

## Before you report
- Typecheck or compile the touched modules, then run the affected suites.
- Merge `<integration>` into your branch and re-run the affected suites.
- Run the full suite once, with a private log path (`mktemp`), and read the log yourself.
- Run <repo-specific verification, e.g. bundle-check, a regeneration diff>.
- **Time the affected suites** on the integration tip (the base) and on your head, with the same
  command (<timing command, e.g. `/usr/bin/time -f %e <test cmd> --suite X`, or `pytest --durations=15`>).
  Use the full-suite log's per-suite times too. If a suite got more than 20% or 30 s slower, or a new
  test takes more than 5 s, say why it's needed and whether it could sit behind a slow marker,
  use a smaller fixture, or share setup.

## Report
Write `<run-dir>/reports/<n>.md`, then reply with only that path. Keep it to about 400 words,
in this shape:
- **Result:** one sentence.
- **Evidence:** suite counts with log paths, verification diffs with paths, and the test you saw fail first.
- **Test time:** for each affected suite, base and head seconds, and the full-suite wall time; justify any growth.
- **Commits:** the hashes and subjects.
- **Decisions taken:** what, and why.
- **Decisions needed:** the question, the options with counts or examples, your recommendation.
- **Outside your lane:** anything you touched outside it, and why.
```

## Fix-round prompt (same lane)

Send it with `lane.sh prompt <name> <file>`. Write the fix list to `briefs/<n>-fix<k>.md`
and keep it in this shape:

```markdown
Review fixes for #<n>. Same rules as your brief: TDD for behaviour changes, commit by explicit paths, don't push.

## Rulings on your decisions
- <decision>: accepted / changed to <…>, because <…>.

## Must fix
1. <finding, with file:line and the rule or spec line it breaks, and the fix you want>
…

## Clean-ups
- <…>

Then run the affected suites, merge `<integration>`, run the full suite once, and update `<run-dir>/reports/<n>.md` (append a "Fix round <k>" section). Reply with only the path.
```
