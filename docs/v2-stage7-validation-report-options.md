# Stage 7 options memo — ValidationReport construction

Status: **Decision required; no Stage 7 code authorized or started (2026-08-18)**

Authority: `docs/v2-product-spec.md`, `docs/v2-state-and-use-cases.md`,
`docs/v2-architecture.md`, and finding A1 / Stage 7 in
`docs/v2-architecture-audit.md`.

## 1. Decision in scope

Stage 7 would unify the three independent `ValidationReport` construction paths in:

- `domain/validation.py` for draft/content validation;
- `infrastructure/rendering.py` for render/PDF/ATS validation; and
- `application/ready.py` for current Ready-integrity verification.

This memo makes no code or data change. Before implementation, the user must decide:

1. whether to rename the two different groups currently called `"filename"`;
2. whether historical `validation_runs.report_json` rows are rewritten or retained
   under an explicitly versioned report shape; and
3. whether the shared pass formula always includes the hard-issue term.

## 2. Current behavior and stored shape

The constructors currently use these formulas:

| Producer | Current formula | Current `"filename"` meaning |
| --- | --- | --- |
| Draft validation | `all(groups.values()) and not any(issue.hard ...)` | Headline safety (`unsafe-headline`) |
| Render validation | `all(groups.values())` | Recruiter-facing PDF filename |
| Ready integrity | `all(groups.values())` | No `"filename"` group; its own integrity group set |

`ValidationReport` itself already rejects `passed=True` when any group is false or any
hard issue exists. Every current render and Ready issue site also sets its corresponding
group false. Consequently, the missing hard term in the render/Ready formulas is latent:
it does not produce a currently passing report with a hard issue.

Reports are stored as the model's direct JSON in immutable `validation_runs.report_json`
rows. There is no report-shape version field today. The database's immutable-table
triggers reject updates and deletes of historical validation rows.

## 3. Group-name options

### Option A — keep both `"filename"` names

Draft and render reports retain their current keys, and the common factory accepts that
the same name has phase-specific meaning.

Consequences:

- No group-key migration or immediate client change.
- Historical and new rows remain superficially compatible.
- The ambiguity that caused A1 remains: a consumer cannot interpret `"filename"`
  without also knowing the phase.
- A future combined validation summary can accidentally merge unrelated concepts.
- Documentation must permanently define the phase-dependent meanings.

### Option B — rename only the headline-safety group

New draft/content reports use `"headline_safety"`; render reports keep `"filename"` for
the actual PDF filename.

Consequences:

- Each name has one meaning.
- The render key remains aligned with v1's Ready group 10, “Filename and metadata
  validation.”
- Only pre-render report consumers need a new group key.
- Historical rows still contain `"filename"` for headline safety, so report-shape
  versioning is required to interpret them correctly.

### Option C — rename both groups

New reports use `"headline_safety"` and `"artifact_filename"`.

Consequences:

- Maximum local clarity and no generic name.
- More client, test, documentation, and compatibility churn than Option B.
- Renames the render key even though its current meaning matches the product contract.
- Historical interpretation still requires report-shape versioning.

## 4. Historical-row options

### Option 1 — back-fill `validation_runs.report_json`

Rewrite historical JSON so every row uses the new group names/version.

Consequences:

- Queries see one apparent shape.
- Historical validation evidence is no longer byte-for-byte immutable.
- The existing immutable-table trigger must be bypassed or replaced during migration.
- Backup, restore, migration, reconciliation, and complete row-accounting gates become
  mandatory before the rewrite.
- A mistaken phase mapping could silently change the meaning of historical evidence.

This conflicts with the product's immutable-history posture and is not recommended.

### Option 2 — version new reports and preserve old rows

Keep every historical JSON payload unchanged. Treat an absent report-shape version as
legacy v1, and write an explicit new version on Stage 7 reports. Readers support both
shapes and interpret legacy `"filename"` using the stored phase.

Consequences:

- Historical evidence remains immutable and auditable.
- New reports can use unambiguous group names.
- Readers and API projections need explicit v1/v2 compatibility logic.
- Fixtures and migration tests must cover both shapes.
- The version should be carried in the report JSON itself (for example,
  `report_schema_version`) so exported evidence remains self-describing rather than
  relying only on a database column.

### Option 3 — write old and new aliases together

New reports contain both legacy and renamed keys.

Consequences:

- Older consumers may continue to work temporarily.
- Two keys describe one outcome and can disagree.
- The ambiguity becomes part of the new persisted contract instead of being retired.
- A later removal requires another shape transition.

This is not recommended.

## 5. Effect of adding the hard-issue term

The proposed shared formula is:

```text
passed = all(groups.values()) and not any(issue.hard for issue in issues)
```

For current production paths, this changes no passing outcome:

- every current hard render/Ready issue also makes a group false;
- soft warnings remain non-blocking; and
- `ValidationReport` already refuses a contradictory passing report with a hard issue.

The observable difference appears only if a future producer adds a hard issue without
also clearing a group. Today, `passed=all(groups.values())` would supply `True`, after
which model validation raises an exception. With the shared formula, the same findings
produce a normal executed validation result with `passed=false`. That is a change from
validator execution failure to explicit domain failure, not from a currently passing
outcome to a failing one.

Before any implementation, characterization tests should prove:

- all current render and Ready issues still fail the same groups;
- a soft issue with all groups true still passes;
- a hard issue with all groups true produces `passed=false` through the factory; and
- legacy stored reports deserialize without reinterpretation.

## 6. Recommendation

Adopt the following package as one decision:

1. **Rename only the draft/content group to `"headline_safety"`; keep the render group
   as `"filename"`** (group-name Option B).
2. **Preserve historical rows and version the new report shape** (historical Option 2).
   An absent version means legacy v1; Stage 7 writes a new explicit version.
3. **Use one domain-owned factory that derives `passed` and never accepts it from the
   caller**, with the formula including both group results and hard issues.
4. **Do not dual-write aliases and do not back-fill immutable validation rows.**

This recommendation gives each group one meaning, preserves the render name that
already matches the product contract, keeps historical evidence immutable, and turns a
future inconsistent hard issue into an ordinary blocking result rather than a validator
execution exception. Its cost is deliberate dual-shape read compatibility, which is
safer and more transparent than rewriting history.

## 7. Decision required before code

The user must approve or replace each choice below before Stage 7 begins:

- Group naming: keep both / rename headline only / rename both.
- History: back-fill / version without back-fill / dual aliases.
- Pass rule: shared groups-plus-hard formula / another explicitly stated rule.

No Stage 7 implementation, schema change, historical-row mutation, or Stage 8 work is
authorized by this memo.
