# Orchestrating Store build epics

Load this for an `opengwasdb-stores` epic that obtains data, produces a Release
Bundle or runs Store Release Build, including `/create-store`'s three-stage
epics. It supplements the main procedure; code-only epics use that procedure
unchanged. Read the repo's agent instructions, current contracts and ADRs.
The epic's **Store build orchestration** section holds its agreed contract and
gate owners. If it lacks a settled contract, stop for alignment rather than
turning scientific choices into worker defaults.

## 1. Classify the graph

For each ticket, distinguish **code**, **registry/metadata**, and **operation**
work. One ticket can contain all three; completing its code does not complete
its operation. For a new Store, preserve the serial chain:

```text
Obtain source → Create release bundle → Run build
```

Parallelise only genuinely independent prerequisite/implementation work within
the lane/resource budget. Detect acquisition/builds already running on another
host or checkout before starting anything. Keep capability prerequisites in
sibling repos explicit; do not bypass them with local scientific implementations.

Record the stage, required evidence and gates in each ticket's `note`, brief and
report. The existing `state.json` statuses suffice:

- `needs-decision`: a scientific choice, bundle acceptance, rehearsal go/no-go
  or execution/publication approval needs the named human. Put the question in
  `questions`; use `board_note` to keep the gate visible in the epic's Next.
- `waiting-external`: data, access, Reference Resource, engine capability,
  required base-branch landing or compute is unavailable. Add the exact release
  condition to `waiting_external` and the ticket note.
- `frontier`: all blockers are satisfied for the next authorised action, not
  merely because a prerequisite's code merged.

Keep blocked downstream tickets blocked until the upstream stage's full
acceptance criteria, including operational evidence and approvals, are met.
A closed legacy ticket is not proof of a current artifact; inspect its evidence.

## 2. Plan gates before lanes

The dry run is still read-only outside the run directory. Include the host,
resource budget, proposed commands, evidence destinations, human gates and
resumption plan in `plan.md` and frontier briefs. Do not acquire, freeze,
resolve, emit, accept, rehearse or build as part of an orchestration dry run.
You may read existing receipts and command help; write proposed commands only.

During a real run, code lanes use the main implementer chain and TDD. Scientific
policy/identity decisions and real-data operations need an operator or an
explicitly briefed Sonnet/Opus lane with bounded permissions and independent
review. A cheap unattended worker is not the production operator. Allocate
resources across all active builds, not just this epic's lane count.

Every operational brief specifies:
- input revision, ids/checksums and exact Selection; allowed output paths;
- operator/host, runtime pin, command, resource/time budget and permission scope;
- required source/reference checks, logs/receipts and success criteria;
- stop gates, decision owner, safe resumption procedure and report path.

Use the main brief template for code portions. For operation-only work, replace
TDD/test-time sections with reproducibility, integrity and real-data verification
criteria; never invent a failing unit test for a download or claim that tests
prove the production artifact. Keep relevant repo checks for committed evidence.

## 3. Enforce the three stage boundaries

**Obtain source.** Verify the authoritative intended set against acquisition
availability and provenance. Reuse verified data; make unexplained omissions,
duplicates, changed identity or ambiguous source semantics a stop gate. Small
connector/integrity evidence is the deliverable in Git, not raw files or secrets.

**Create release bundle.** Freeze the agreed Selection, resolve using the pinned
engine, apply agreed policy and emit a candidate through Manifest Generation.
Present concrete membership, exclusions/warnings, identity mapping, ancestry and
effect-scale evidence to the named human. Wait for their explicit acceptance
of that exact bundle revision/checksums; record it and the accepted transition.
The orchestrator/reviewer cannot self-accept on the basis of green tests. If
review changes a material input, repeat the relevant gate. Only then can this
stage's evidence be reviewed and merged and the build frontier open.

**Run build.** Prove accepted-input identity, source/reference integrity, runtime
and resource readiness. Inspect the supported release dry-run plan. Before a
costly or publishing command, obtain explicit approval of command, host, budget
and publication effect; permission to orchestrate or file issues is insufficient.
An explicit user authorisation may cover those named actions up front; record
its scope rather than repeatedly asking. Rehearsal go/no-go remains a separate
gate when required. If `dev` landing is required first, wait for the user's PR
merge; do not merge to the base yourself.

Use the current supported `pixi run release <store-id>` entry point. It may
publish automatically on success: approval must cover that effect **before**
launch, not after validation. Never silently switch to raw Snakemake or bypass
runtime, status or safety refusals. Force/replacement and recovery that discards
artifacts require separate approval. Keep acquisition/generation/build separate;
a changed config must not silently regenerate accepted input during a build.

Read terminal records and actual validation outputs. Verify built membership by
Analysis IDs through supported engine interfaces, plus the contract's layout,
coverage, completion and required indexes. For completion, require the applicable
Observed-View Check and publication evidence under the current ADRs. Record
warnings and deviations; missing/unknown evidence is not a pass.

## 4. Review, merge and finish

Keep the normal integration branch, draft PR/dashboard and two-axis reviews.
Standards review covers repository boundaries, immutable inputs, reproducibility
and small evidence artifacts; Spec review checks the actual source/bundle/Store
against the epic contract and every gate. Check reports against receipts and
artifacts, not worker claims. Large artifacts/logs remain outside Git, with
stable references and digests in small committed receipts.

An operational ticket reaches `merged` **only after** its real operation and all
acceptance criteria pass, its evidence has independent review, and the evidence
commit merges into the integration branch. For already completed work, commit
verified reconciliation evidence rather than a fake implementation/kickoff
commit. A launch, running process, generated script, candidate bundle or an
unexecuted runbook cannot close a stage ticket.

Until then keep the ticket in the appropriate live/gated state; leave durable
job identity, host, input hash, last checked receipt and next action in state and
reports so resumption inspects the existing run rather than launching a second.
This keeps `board.py sync-run`'s merge-based closing semantics truthful without
adding a second operational status system.

At the main procedure's final review, check the entire chain's scientific and
operational evidence as well as code. If a merged stage lacks required evidence,
reopen it and set `fixing`/the appropriate gate. A waiting build means the epic
is still incomplete; show the blocker even if a preparatory PR is ready. The
epic stays open until all stage criteria pass and its final work lands on the
base branch; the user's final PR merge remains their decision.
