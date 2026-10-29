# Project site: the epic record and the yardstick

Only for a repo with `docs/spec/project-site.md`. Its "The epic record" section and
`src/project_site/records.py` are the contract; `docs/spec/yardstick.md` defines the
yardstick. Read the section if you hand-edit a record.

## The record

`epic_record.py` builds every field from `state.json` (and any `state-stage*.json` beside it,
earlier stages first). It never invents a value: unknown is `null`. It takes the summary
from the file you write, never generates it.

Optional `state.json` keys it copies, set them as you learn them:

| Key | Becomes |
|---|---|
| `workstream` | `workstream` (a board Workstream; `board.py` shows it) |
| `finished` | an ISO date: the epic issue is closed. Otherwise `status: active`, `finished: null`. A finished run does not finish its epic: the owner's merge does. |
| `yardstick`, `catalog` | `{before, after}` |
| `versions` | tags the PRs shipped |

Tickets with no `issue` take their key from the entry name (`386`, `odb333`), else `null`.
`merge` is a commit only when the entry's `merge` or `merge_commit` *starts* with a 7–40 hex
hash (`1ad7685 + 1f1d2fa (final fixes)` gives `1ad7685`); any other text gives `null`. `prs` come from
`pr`, `pr_merged` and the tickets' `pr`. `started` is the earliest decision's date unless
`state.json` sets `started`.

Validate with the repo's own environment (no environment of the skill's):

```bash
pixi run -e dev python -c "import sys,yaml; from project_site.records import validate_epic; \
f=sys.argv[1]; print(validate_epic(yaml.safe_load(open(f)), f.rsplit('/',1)[-1]) or 'valid')" docs/_epics/<repo>-<n>.yaml
```

## The yardstick

`pixi run yardstick` writes `docs/_yardstick/<UTC start>-<opengwasdb version>.json`. It is
read-only on the Artifact Root and takes about 90 s. A run overlapping 00:00–11:00 local is
flagged `veeam_window` (the nightly snapshot throttles I/O); a loaded host skews it too. So
run it after 11:00 with the lanes idle, and check the load average first. Otherwise defer it
and say so in `board_note`.

`before` is the newest committed result whose `opengwasdb.revision` equals the revision the
base branch's `pixi.lock` pins; `null` if none. The first epic after a re-pin has none.

## Catalog versions

Only when the epic changes Store data. `catalog.before` is the current version directory
name (16 hex) under the catalog root at the start. `after` is the version the owner's
rebuild produces after the merge, so at finish it is `null`: the owner, who rebuilds the
catalog after the merge, fills it in.
