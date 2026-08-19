# Stage 7 options memo — ValidationReport construction

Status: **Closed.** Stage 7a landed 2026-08-18; Stage 7b landed with M2 boundary 2a
(`docs/v2/records/m2-domain-records.md` D7, §3.4). This file is kept for the option
analysis behind the decision, not as a state record.

Authority: `docs/v2/spec/product-spec.md`, `docs/v2/spec/state-and-use-cases.md`,
`docs/v2/spec/architecture.md`, and finding A1 / Stage 7 in
`docs/v2/records/architecture-audit.md`.

## 1. What was being decided

Stage 7 was defined to unify the three independent `ValidationReport` construction
paths in:

- `domain/validation.py` for draft/content validation;
- `infrastructure/rendering.py` for render/PDF/ATS validation; and
- `application/ready.py` for current Ready-integrity verification.

The work was split so the pass-rule invariant would not force a persisted-shape
transition immediately before M2's numbered-migration work: 7a landed the domain-owned
factory with no shape change, and 7b carried the group rename and the report schema
version into M2's migrations. Sections 3–5 record the options; section 6 records what
was accepted. The accepted target is stated once, in section 6.

## 2. Behavior and stored shape before Stage 7

The three constructors used these formulas:

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

Stage 7a characterization tests prove:

- all current render and Ready issues still fail the same groups;
- a soft issue with all groups true still passes;
- a hard issue with all groups true produces `passed=false` through the factory; and
- legacy stored reports deserialize without reinterpretation.

## 6. Accepted decision

The user accepted the following target, split across 7a and 7b:

1. **Rename only the draft/content group to `"headline_safety"`; keep the render group
   as `"filename"`** (group-name Option B).
2. **Preserve historical rows and version the new report shape** (historical Option 2).
   An absent version means legacy v1; Stage 7b writes a new explicit version with M2.
3. **Use one domain-owned factory that derives `passed` and never accepts it from the
   caller**, with the formula including both group results and hard issues.
4. **Do not dual-write aliases and do not back-fill immutable validation rows.**

This decision gives each group one meaning, preserves the render name that
already matches the product contract, keeps historical evidence immutable, and turns a
future inconsistent hard issue into an ordinary blocking result rather than a validator
execution exception. Stage 7a realizes only the factory portion. Stage 7b deliberately
absorbs the dual-shape compatibility cost into M2 so there is one persisted-shape
transition rather than two.

The 7b naming documentation must also preserve an important coupling: draft headline
safety and render filename policy both consume `Profile.safe_headlines`, and
`Profile.validate_default_emphasis` requires `normalized_role` to be a safe headline.
The distinct group names describe distinct findings, not independent policy inputs.

## 7. Stage boundary

Stage 7a is behavior-preserving: no threshold, message, exception type, group name,
status, public signature, stored report shape, artifact path, or fact semantic changed.

No schema field, group rename, compatibility reader, historical-row mutation, or Stage 8
work was performed in 7a; all of it landed later, in M2 boundary 2a.
