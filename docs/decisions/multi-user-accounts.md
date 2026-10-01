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
   `CandidateContext` moves from `base/candidate.json` to one `candidate_contexts` row
   per user, with the same fields (architecture §18.2).
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
   `omitted_roles`) move to a per-user binding in PostgreSQL. A user's binding comes
   from `import-knowledge` and changes only through `attach_fact` and
   `confirm_and_use_fact`; nothing derives it automatically. Web editing of Profiles
   stays a non-goal.
9. **An account ends by deactivation, never deletion.** The contract is deactivate,
   revoke every session, and anonymize the PII in a named list of mutable fields
   (state-and-use-cases §23). Immutable triggers are not bypassed for a user lifecycle, and immutable records (Submissions, JobSnapshots,
   the AI call log, audit, fact events) stay, owned by a user row that no longer
   identifies anyone. A hard delete is only ever an explicit, separately approved
   operator procedure, never part of the API.
10. **Rate limiting and AI quota live in PostgreSQL.** There is no Redis (architecture
    §2). Sign-in is the only rate-limited route: a fixed window, a temporary throttle,
    no permanent lockout. A per-user AI quota
    is counted from the user's own Operations, so no counter can drift from the work it
    counts.
11. **The first user is created by CLI.** An existing single-candidate installation is
    assigned to that user. The CLI requires a real email address; the migration never
    invents one.
12. **No self sign-up for now; the operator creates users.** Today there is one user,
    the operator. With no sign-up there is no email to verify, so the whole email side —
    verification, reset by email, email change, single-use tokens, and SMTP — is not
    built. A forgotten password is reset with `set-password` on the CLI. A new user's
    first facts come from `import-knowledge`, so onboarding needs no new screen.
13. **Keep the account model minimal.** A session has one absolute lifetime (no idle
    timeout, no refresh). Account events store the event and the user only, no IP or
    email. Password hashes use the library defaults, with no rehash policy.

Defaults adopted with this decision: the exact limits (session lifetime, sign-in window,
quota size) are configuration with the defaults stated in architecture §18.

## 3. Rejected

- **A `user_id` column on every table.** It duplicates ownership that the Application
  already carries. A duplicated owner can disagree with the root, and then no one knows
  which one wins.
- **JWT in `localStorage`, or JWT with a refresh token.** Readable by any script on the
  origin, and not revocable without a server-side list, which is a session table anyway.
- **Self sign-up with email verification, now.** One user does not need it, and it
  brings SMTP, tokens, enumeration defences, and more rate limits. It returns as its own
  decision if the product opens to other people.
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
   `auth_events`, `rate_limit_buckets`) and the per-user Knowledge and settings tables.
2. **Operator:** `create-user --email <real address>` creates the one user and prompts
   for a password.
3. **Operator:** `import-knowledge --user <id> --from base/` reads `base/*.json`,
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
6. `app_settings` (one row) becomes that user's `user_settings` row, keyed by
   `user_id`. Existing
   `knowledge_mutation_journal` rows stay read-only history. A `PREPARED` or
   `QUARANTINED` entry refuses the upgrade until an operator resolves it on the old
   version.
7. Storage keys do not change. They already embed the Application ID, and ownership of
   a payload comes from its registered reference, not from its key (architecture §6.2).

After the upgrade, `base/` and the candidate-specific parts of `profiles/` are import
input only. They are no longer read at runtime.

## 5. Delivery order

Each step is its own pull request and brings the focused tests for what it changes, as
`CLAUDE.md` requires. Data model and isolation come before any sign-in surface: a
system that can identify a user but does not yet isolate their data is the state to
avoid.

1. **Specs and decision records** (this change). Documentation only.
2. **Users, sessions, bootstrap CLI:** `users`, `user_sessions`, `auth_events`;
   `create-user` and `set-password`. No route yet.
3. **Per-user Knowledge:** `facts`, `candidate_contexts`, `profile_bindings`
   (architecture §18.2); `import-knowledge`; the journal retired; the Profile
   template/binding split. The riskiest step for fact semantics.
4. **Ownership on Application and settings:** `applications.user_id`, `user_settings`,
   the existing installation assigned to its one user (§4).
5. **Repository and query isolation:** every service resolves through the `Actor`
   (architecture §18.3); every list, count, and duplicate check scoped.
6. **Idempotency, fairness, and worker isolation:** the per-Application idempotency key,
   fairness between users in the claim order (a user with nothing running is served
   first; architecture §18.3), owner derived from the Operation's Application. The
   per-user AI slot first planned here is replaced: the lease table it would have used
   is gone, and a slot would leave a thread idle while a lone user waits.
7. **Auth API and frontend:** `login`, `logout`, `logout-all`, `me`, `change-password`,
   `deactivate_account`; the sign-in and account screens, the auth state, clearing
   per-user browser state. From here every route requires a session.
8. **Email verification and reset — not scheduled.** Decision 12 leaves them out while
   users are created by the operator. They return only with a decision to open sign-up.
9. **Quotas and rate limiting:** the sign-in limit and the per-user AI quota.
10. **Renderer hardening** (architecture §18.6).
11. **Derived isolation gates made complete and blocking:** the cross-user route
    matrix, the schema ownership guard, and the persistence-port guard over the whole
    surface, in CI. Steps 5 and 6 already introduce them for what they touch; this step
    closes their exception lists. Only after it does `create-user` accept a second
    user.
12. **Hosted deployment:** public origin, Host allowlist, HSTS, and the hosting
    decisions in §6.

## 6. Open items

1. **PII retained in immutable records after deactivation.** JobSnapshots,
   Submissions, the AI call log (`ai_calls`), and `fact_events.fact_json` keep the candidate's name
   and contacts. Anonymization makes them unreachable and unlinked to an identity; it
   does not erase them. Whether that is acceptable matters once there is a second user;
   it is a legal decision, not a technical one.
2. **Numeric limits.** The defaults in architecture §18 are starting values, not
   measured ones.
3. **Hosting.** Where it runs, who terminates TLS, and PostgreSQL and bucket backup are
   the operator's choice and are not specified here; step 12 needs them decided.
