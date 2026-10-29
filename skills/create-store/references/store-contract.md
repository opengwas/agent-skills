# Store contract checklist

Use this during alignment, then record the settled contract in the epic. Each
row needs a value and evidence/decision, a reason it is not applicable, or a
named blocker with an owner and release condition. These are questions to
settle, not a second schema: current repository contracts and ADRs govern.

## Purpose and shape

- What query/scientific promise does this release make? Production or a
  deliberately small Trial Store Release? What is explicitly out of scope?
- Store Layout (dense, ragged, hybrid), observed-only or reference-completed,
  Association Coverage (full GWAS, cis, trans, signals, etc.) and variant axis.
  Confirm the pinned engine can produce and resolve this combination.
- For completion: required or deliberately out of scope? Matching LD panel,
  ancestry, genome build, variant convention and qualification evidence. An
  unavailable panel is a blocker, never an implicit observed-only opt-out.
  Follow current single-id completion policy; legacy two-id examples do not
  justify allocating a new observed/completed pair.
- Required post-build artifacts and query indexes, including the current
  Indexed Variant Subset defaults or an explicit justified opt-out.

## Source and Selection

- Source Provider, homogeneous Source Collection, release/version/date, URLs,
  publication, licence, Access Posture and permission to acquire/use the data.
  Separate collections when files need different Column Maps/reader semantics.
- Existing local data or new acquisition? Authoritative intended Analyses,
  exact Selection rule/list, expected counts/bounds, ancestry groups, trait or
  target scope. A directory listing is availability, not intended membership.
- Acquisition Manifest and Source Metadata Table producer; checksums, sizes,
  original-file provenance, snapshot naming and resumability. Explain missing
  files, duplicates, per-Analysis splitting, conversion and region filtering.
- Source Format, Source Reader Capability and Column Map: coordinate build,
  effect/reference alleles, frequency orientation, p-value representation,
  effect scale/units, missing-value tokens and sample-size semantics. Name
  unsupported capabilities as prerequisites in `opengwasdb`.

## Identity

- Proposed opaque `OGS-` Store id and source-natural label; check registered
  releases **and reservations in issues/configs/active branches** before
  proposing allocation. Recheck immediately before emitting. Never assume
  max-on-disk plus one is unreserved or reuse an assigned id.
- Source Collection id, snapshot id, release lineage and any superseded release.
- Registry Analysis ID format with real examples and a deterministic mapping
  from Source Analysis ID: namespace, version, ancestry/sex/stratum/target
  components where needed, punctuation/escaping and collision handling. Show
  why it is stable and unique over the intended scope; preserve upstream IDs
  separately. Use the current connector's explicit identity fields rather than
  renaming resolver keys or inferring identity from file order.
- Distinguish Trait IDs, Source Trait IDs and Analysis IDs. Agree Analysis Labels,
  analysis groups, Trait Ontology Mapping and target annotation where relevant.

## Scientific policy

- Selection ancestry expectation: single super-population or multi-ancestry?
  Distinguish Source Ancestry Labels from measured Assigned Ancestry; agree
  ancestry references, fit gates and handling of mismatch/unassigned/no-AF.
  Source fallback or keeping unassigned Analyses requires explicit opt-in and
  recorded warnings under the current policy. Never silently relabel or move
  an Analysis to a different release.
- Distinguish membership filters, association-row filters and optional query
  indexes. State thresholds, units and the stage that enforces each: MAF,
  INFO, region/cis window, p-value, missingness and other requested exclusions.
  Preserve positions needed for resolution QC when region-filtering sources.
- Store Composition Rule and handling of MAF-unfiltered Analyses; separate
  releases if required by policy rather than weakening a shared Store's rule.
- Effect-scale/phenotype-SD rules, quantitative vs case-control counts, sample
  size kind, allele alignment and genome harmonisation; reference versions and
  thresholds. Absence stays distinct from zero and reference-derived values.
- Quality Checks: which findings exclude and which warn? Agree allowable
  losses, discrepancy handling and evidence needed to accept the concrete
  admitted/excluded membership. Source counts may be expectations; measured
  results, not guessed numbers, decide acceptance.

## Execution and gates

- Execution host/operator, pinned runtime, cores/memory/disk, anticipated data
  volume/time/cost, download limits, Artifact Root, Work Root and Resolution
  Area. Deployment paths stay out of immutable bundle identity/Build Recipe.
- Concurrent runs or existing published artifacts for this id? Define exclusive
  ownership, interruption/resumption and whether replacement is requested.
- Name the human who accepts the exact candidate bundle, the approver of
  acquisition/compute/publication, and the evidence reviewer. Agree whether a
  Rehearsal Run is needed, its representative scope and review gate before the
  full run; a Preflight is not a build or a rehearsal.
- Define acceptance evidence: intended/available/admitted/excluded membership,
  actual built Analysis ID equality (not just counts), expected layout/coverage,
  validation verdict and warnings, required completion and indexes, provenance,
  executed commands/runtime and registered reports. State what must reach
  the base branch before operational execution and who unblocks that landing.
