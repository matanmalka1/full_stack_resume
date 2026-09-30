# Decision: user accounts and per-user isolation

Status: **approved, not implemented** (2026-09-30). The specifications carry the binding
rules, each marked *designed, not built* until it ships:
[`product-spec.md`](../spec/product-spec.md) §22,
[`state-and-use-cases.md`](../spec/state-and-use-cases.md) §23,
[`architecture.md`](../spec/architecture.md) §18, and
[`test-and-acceptance-plan.md`](../spec/test-and-acceptance-plan.md) §3.11. This record
keeps why, what was rejected, how the single-candidate installation maps onto the new
model, and the delivery order. It does not restate the rules.

## 1. Why

The product was a local tool for one candidate. There was no authentication, and the
only security boundary was loopback plus an Origin check. It now becomes a hosted service
where each user is one candidate and must reach only their own data. That changes the
deployment model and removes a product non-goal (product-spec §5, §21), so the specs are
changed before any code.

The login screen is the easy part. The risk is **isolation**: one query that resolves a
record by ID without its owner is an IDOR, and it leaks a candidate's CV, contacts, and
job history to another user. Every decision below is judged first by what it does to
isolation.

## 2. Decisions

1. **One user is one candidate.** No candidate selector, no second candidate per user.
   `CandidateContext` becomes per-user state instead of a file.
2. **Authentication is always on.** There is one runtime mode. Local development creates
   a user through the CLI and logs in. No setting disables authentication, because a
   switch like that is where a production hole comes from.
3. **Opaque server-side sessions, no JWT, no refresh endpoint.** A random token in an
   `HttpOnly` cookie; only its hash is stored (`user_sessions`). Revocation and
   logout-everywhere become a row update. A refresh token adds nothing on top of a
   revocable server-side session.
4. **CSRF by `SameSite=Lax` plus the existing Origin check on every mutation.** No CSRF
   token. The Origin middleware stays and now also guards login.
5. **Cross-user access is `404`, never `403`.** Another user's record cannot be told
   apart from one that does not exist.
6. **Ownership goes through the aggregate root.** `user_id` sits on roots only: `users`
   → `applications`, and the user-level Knowledge, settings, and auth tables. A child is
   resolved through an Application already resolved for the user:

   ```python
   application = applications.get_for_user(tx, application_id, user_id)
   analysis = analyses.get_for_application(tx, analysis_id, application.id)
   ```

   `user_id` is not spread across every persistence method. A child addressed by its own
   ID (an Operation, an artifact version) joins to its root in the same query.
7. **Knowledge moves to PostgreSQL and is user-scoped.** `base/*.json` stops being a
   runtime source. A canonical fact belongs to a user, not to an Application;
   Applications only reference facts. The Knowledge mutation journal existed only
   because a fact change crossed a file and the database. Once both are in one
   transaction it has no job, so it is retired (§4).
8. **Profiles: a shared template plus a per-user binding.** Track, sections,
   `max_claims`, emphases, and tag weights stay a version-controlled system file. The
   parts that name one candidate's facts (section pools, pins, `safe_headlines`,
   `omitted_roles`) move to a per-user binding in PostgreSQL. A new user's binding is
   derived from the tags on their own facts, so a new user can reach a CV from facts
   alone. Web editing of Profiles stays a non-goal.
9. **Account deletion is deactivation plus anonymization, never a hard delete.**
   Immutable triggers are not bypassed for a user lifecycle. Mutable PII is erased,
   sessions and tokens are revoked, and immutable records (Submissions, JobSnapshots,
   provider evidence, audit, fact events) stay, owned by a user row that no longer
   identifies anyone. A hard delete is only ever an explicit, separately approved
   operator procedure, never part of the API.
10. **Rate limiting and AI quota live in PostgreSQL.** There is no Redis (architecture
    §2). Login throttling is progressive, with no permanent lockout. A per-user AI quota
    is counted from the user's own Operations, so no counter can drift from the work it
    counts.
11. **The first user is created by CLI.** An existing single-candidate installation is
    assigned to that user. The CLI requires a real email address; the migration never
    invents one.

Defaults adopted with this decision: the exact limits (session lifetime, token lifetimes,
throttle windows, quota size) are configuration with the defaults stated in architecture
§18. A user must verify their email before any product route, including AI work, opens
to them.

## 3. Rejected

- **A `user_id` column on every table.** It duplicates ownership that the Application
  already carries. A duplicated owner can disagree with the root, and then no one knows
  which one wins.
- **JWT in `localStorage`, or JWT with a refresh token.** Readable by any script on the
  origin, and not revocable without a server-side list, which is a session table anyway.
- **A local no-auth mode.** Two security models to test, and a flag that can ship
  switched on.
- **Bypassing immutability triggers to delete an account.** It breaks the one
  architectural guarantee that protects evidence nothing else can reproduce.
- **PostgreSQL row-level security as the isolation mechanism, for now.** It would be a
  strong second line, but the worker and the transaction-token model would both need a
  per-transaction user setting before it helps. Isolation is enforced in the application
  layer and proved by a derived cross-user test (test plan §3.11). This can be revisited.
- **Keeping facts in files, one directory per user.** Not transactional with the
  database, and it keeps the journal and quarantine machinery alive only to paper over
  that.

## 4. Mapping the single-candidate installation

A fresh installation starts empty, and nothing below applies to it. For an existing
installation:

1. **Schema step one:** create the account tables (`users`, `user_sessions`,
   `auth_tokens`, `auth_events`, `rate_limit_buckets`) and the per-user Knowledge and
   settings tables.
2. **Operator:** `create-user --email <real address>` creates the one user and prompts
   for a password.
3. **Operator:** `import-knowledge --user <id>` reads `base/*.json`,
   `base/candidate.json`, and the candidate-specific parts of `profiles/*.yaml` into that
   user's Knowledge in one transaction. It refuses when the user already has facts.
   Existing semantic fact IDs (`common.contact.email`, …) keep their exact spelling for
   that user, so every existing document, Submission, and fact event still resolves.
4. **Schema step two:** add `applications.user_id`, assign every existing row to the one
   user, then make it `NOT NULL`. The revision refuses when rows exist and the user
   count is not exactly one. The owner is derived from the fact that the installation
   had one candidate; nothing is guessed.
5. `fact_events` rows without an `application_id` get their owner through a *permitted
   transition*: the guard allows exactly `user_id: NULL → value`, once, with no other
   column changing. That is the same pattern that already guards terminal Operation rows
   (architecture §6.1), not a trigger bypass.
6. `app_settings` (one row) becomes that user's settings row. Existing
   `knowledge_mutation_journal` rows stay read-only history. A `PREPARED` or
   `QUARANTINED` entry refuses the upgrade until an operator resolves it on the old
   version.
7. Storage keys do not change. They already embed the Application ID, and ownership of
   a payload comes from its registered reference, not from its key (architecture §6.2).

After the upgrade, `base/` and the candidate-specific parts of `profiles/` are import
input only. They are no longer read at runtime.

## 5. Delivery order

Each step is its own pull request, with the gates `CLAUDE.md` assigns to it.

1. **Spec migration** (this change). Documentation only.
2. **Knowledge to PostgreSQL**, still single-user: the fact tables, the import CLI,
   retiring the journal, the Profile template/binding split. The riskiest step for
   fact semantics, and it does not depend on accounts.
3. **Identity and sessions:** the account tables, the account commands, cookie sessions,
   rate limiting, auth audit, the email port, and the bootstrap CLI.
4. **Ownership:** `applications.user_id`, per-user settings, ownership-scoped
   resolution in every service and in the worker, per-application idempotency, and the
   derived cross-user guards. From this step on, every route requires a session.
5. **Frontend:** the auth state, the account screens, and clearing per-user browser
   state on logout.
6. **Production hardening:** public origin and Host allowlist, HTTPS-only cookies and
   HSTS, network-blocked rendering, AI quota, and account deactivation.

## 6. Open items

1. **Onboarding a new user's identity.** A new user has no name or contact facts and no
   `CandidateContext` references. Proposed default: `CandidateContext` is derived from
   the user's canonical facts by tag (`identity` for the name, `contact` for contacts),
   and rendering is refused with a named precondition until a name fact exists. The
   alternative is a small explicit command to set it. Needs a decision before step 2.
2. **PII retained in immutable records after account deletion.** JobSnapshots,
   Submissions, provider evidence, and `fact_events.fact_json` keep the candidate's name
   and contacts. Anonymization makes them unreachable and unlinked to an identity; it
   does not erase them. Whether that is acceptable for the jurisdictions served is a
   legal decision, not a technical one.
3. **Numeric limits.** The defaults in architecture §18 are starting values, not
   measured ones.
