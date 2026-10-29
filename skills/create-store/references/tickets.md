# Epic and stage ticket content

Substitute agreed values; remove inapplicable branches with a reason. Keep the
contract in the epic, and link to it from each ticket rather than copying it.
Use the repo's vocabulary and current commands, not historical Phase A/B names.

## Epic: Build <label> (<store-id>)

- **Outcome:** the Store's scientific/query promise, scope and non-goals.
- **Agreed Store contract:** the completed `store-contract.md` checklist, with
  evidence links, decisions and named blockers. This is the source of truth.
- **Existing assets and prerequisites:** reusable inputs and linked capability
  issues; distinguish measured facts from estimates to verify.
- **Completion criteria:** reproducible source identity, accepted Release Bundle,
  built and validated Store with required completion/indexes, exact membership
  reconciliation, and reviewed evidence landed on the repo's integration base.
- **Store build orchestration:** obtain source → create release bundle → run
  build, using native sub-issues/dependencies. Name acceptance, execution and
  review owners; point `/orchestrate` to its `references/store-builds.md`.
  Record the checkout/base, proposed host/resources, approval gates and evidence
  destinations. No ticket table: GitHub's native sub-issues carry the breakdown.

## Ticket 1: Obtain source for <label> (<store-id>)

**Parent contract:** <epic URL>.

**Deliverable:** acquired or verified source files outside Git, a reproducible
provider adapter/acquisition route where needed, and connector files/evidence
ready for the agreed Selection.

**Blocked by:** <external prerequisite issue links or explicitly none>. Name
any access/data-landing gate and exactly what releases it.

**Acceptance criteria:**
- The authoritative intended Analysis set and its expected counts/bounds are
  recorded independently of files found on disk.
- Acquisition covers the Selection; missing/unavailable files have explicit
  statuses/reasons, and duplicates or unexplained omissions fail loudly.
- Acquisition Manifest records locations, checksums and sizes, plus original
  lineage for splits/conversions/filtering. Required QC positions survive any
  region filtering. Existing files are verified, not trusted by path alone.
- Source Metadata Table preserves source identity and declares the agreed
  registry Analysis ID mapping, with uniqueness/collision evidence and examples.
- Reader/Column Map feasibility and key scientific semantics are verified on
  representative files; any missing shared-engine behavior is a linked blocker.
- Small reproducibility/integrity receipts and applicable tests are committed;
  raw data, credentials and large logs stay outside Git. Restricted locations
  are redacted from public issues/receipts as needed.

**Stop gates:** access not approved, source identity changes, unintended losses,
ambiguous allele/effect semantics or a need to change the agreed Selection.

## Ticket 2: Create release bundle for <label> (<store-id>)

**Parent contract:** <epic URL>.

**Blocked by:** <obtain-source ticket>; <external reader/resolver/reference
issues>. Also record these as native dependencies.

**Deliverable:** a reproducibly generated, human-accepted Release Bundle in
`stores/<store-id>/`, with the generation config and small evidence receipts.

**Acceptance criteria:**
- Recheck Store-id reservations; the release config implements the contract's
  Selection, layout, filters, ancestry policy, references and metadata methods.
- Freeze the Source Inventory from the connectors (or verify a reusable frozen
  snapshot matches this Selection); record provenance and discrepancy results.
  Changed frozen inputs require a new snapshot id.
- Manifest Generation preflight passes, every admitted Analysis has matching
  Resolution Record evidence, and emission uses the shared pipeline. Shared
  statistics/readers/builders remain in `opengwasdb`, not a per-Store substitute.
- Candidate bundle checks pass; membership, identity mapping, exclusions,
  warnings, ancestry and effect-scale evidence are reviewed against the epic.
  Record measured intended/available/admitted/excluded counts and reasons for
  every difference. Unsupported or unmeasured scientific evidence is a blocker.
- A named human explicitly accepts the **exact** candidate revision/checksums
  after seeing that evidence; record the decision and transition to accepted
  under the current contract. Later material changes require renewed review
  and the repository's identity/immutability rules.
- Bundle, config, sidecars and acceptance evidence pass current contract and
  applicable test/index-regeneration checks and are committed for review.

**Stop gates:** acceptance is pending; policy, identity, scientific metadata or
membership would change without agreement; a frozen/accepted input would be
silently overwritten. A generated candidate alone does not finish this ticket.

## Ticket 3: Run build for <label> (<store-id>)

**Parent contract:** <epic URL>.

**Blocked by:** <create-release-bundle ticket>; <runtime/Reference Resource/
compute issues>. Name any required landing on the base branch or human execution gate.

**Deliverable:** the accepted bundle's Store Release built, validated and
published through the supported Store Release Build entry point, with reviewed
operational evidence committed back to the registry.

**Acceptance criteria:**
- Verify the accepted bundle's revision/checksums, pinned runtime/capabilities,
  source/reference identity, declared host, free disk, memory/cores and exclusive
  ownership. Inspect `pixi run release-dry <store-id>` against the agreed scope.
- Obtain explicit approval for the recorded command, host, resource budget and
  publication effect. If agreed, run a representative Rehearsal Run and obtain
  its human go/no-go before the full run. Keep rehearsal artifacts separate
  from the final release; a trial/subset is not the production Store.
- Execute `pixi run release <store-id>` using the approved deployment config;
  complete the required completion and post-build steps. Stay within the
  approved scope; replacement/force or new cost requires separate permission.
- Read terminal records and the validation verdict. Reconcile the actual built
  Analysis ID set with admitted membership, explain losses/warnings, and verify
  layout, coverage, required completion and indexes using supported interfaces.
  Count equality or a process exit alone is insufficient.
- Register-generated Validation Record and small reports identify input revision,
  runtime, planned/executed commands, timestamps, artifact locations and checks.
  Preserve generation/acceptance evidence distinctly from built-Store validation.
  Commit the registry evidence and regenerate the applicable registry views.
- An independent reviewer checks evidence against the contract before the ticket
  branch merges. All required stages have evidence, not a promised follow-up.

**Stop gates:** candidate/unaccepted input, preflight refusal, unavailable
resource/reference, failed validation/reconciliation, changed plan, unapproved
publication/replacement or cost. Report a partial run honestly; preserve resume
artifacts and name the unblock condition instead of marking it complete.
