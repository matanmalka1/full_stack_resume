# Decision: user accounts and per-user isolation

Status: **approved; steps 1 to 4 of §5 implemented** (2026-09-30; delivery order and
scope revised 2026-10-11: login first, held to one user by the database, and what a
single user does not need deferred to §6). The specifications carry the binding
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
9. **Ending an account is deferred (§6).** With one user there is no account to end.
   Whatever contract returns keeps two rules: immutability triggers are never bypassed
   for a user lifecycle, and a hard delete is never part of the API.
10. **The sign-in rate limit lives in PostgreSQL.** There is no Redis (architecture
    §2). Sign-in is the only rate-limited route: a fixed window, a temporary throttle,
    no permanent lockout. A per-user AI quota is deferred (§6).
11. **The first user is created by CLI.** An existing single-candidate installation is
    assigned to that user. The CLI requires a real email address; the migration never
    invents one.
12. **No self sign-up for now; the operator creates users.** Today there is one user,
    the operator. With no sign-up there is no email to verify, so the whole email side —
    verification, reset by email, email change, single-use tokens, and SMTP — is not
    built. A forgotten password is reset with `set-password` on the CLI. A new user's
    first facts come from `import-knowledge`, so onboarding needs no new screen.
13. **Keep the account model minimal.** A user row is its email, its password hash, and
    when it was created; nothing else has a reader yet. A session has one absolute
    lifetime (no idle timeout, no refresh). There is no account-event table: a failed
    sign-in is a server-log line without credentials. Password hashes use the library
    defaults, with no rehash policy.
14. **Login ships before isolation, and the database holds the system to one user until
    isolation is complete.** Identity without isolation is a leak only once a second
    user exists. A unique index over a constant (`users_single_user`) makes a second
    `users` row impossible rather than refused by a check that a race could pass. The
    step that completes isolation drops it in its own migration, so the limit cannot
    lapse by accident. Login is useful on its own, and so is each step after it.

Defaults adopted with this decision: the exact limits (session lifetime, sign-in window) are configuration with the defaults stated in architecture §18.

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
- **Isolation before any sign-in surface** (the original order). It held a working login
  behind the largest steps for a risk that one database constraint removes while there
  is one user (decision 14).
- **Building quota, worker fairness, account events, and deactivation before a second
  user exists.** None of them has a reader or a threat with one user; each returns on a
  stated condition (§6).
- **Keeping facts in files, one directory per user.** Not transactional with the
  database, and it keeps the journal and quarantine machinery alive only to paper over
  that.

## 4. Mapping the single-candidate installation

A fresh installation starts empty, and nothing below applies to it beyond creating its
one user. For an existing installation, in delivery order (§5):

1. **Login steps:** the revision creates `users` and `user_sessions`. The operator runs
   `create-user --email <real address>`, which prompts for a password. Once enforcement
   ships (§5, step 3), every route but sign-in and health needs a session.
2. **Knowledge step:** the revision creates the per-user Knowledge tables. The operator
   runs `import-knowledge --email <address>`, which reads `base/*.json`,
   `base/candidate.json`, and the candidate-specific parts of `profiles/*.yaml` into that
   user's Knowledge in one transaction, and refuses when the user already has Knowledge.
   In the same transaction it gives every existing `fact_events` row that user as its
   owner (revision 0005 adds the column and its guard).
   Run it with the application stopped and immediately before the switch to database
   Knowledge: that switch strips the bindings from `profiles/`, so the files can no
   longer be imported afterwards, and a fact edited in the files after the import never
   reaches the database.
   Existing semantic fact IDs (`common.contact.email`, …) keep their exact spelling for
   that user, so every existing document, Submission, and fact event still resolves.
   `fact_events` rows get their owner through a *permitted transition*: the guard allows
   exactly `user_id: NULL → value`, once, with no other column changing — the pattern
   that already guards terminal Operation rows (architecture §6.1), not a trigger
   bypass. Existing `knowledge_mutation_journal` rows stay read-only history; a
   `PREPARED` or `QUARANTINED` entry refuses the upgrade until an operator resolves it on
   the old version.
3. **Ownership step:** add `applications.user_id`, assign every existing row to the one
   user, then make it `NOT NULL`. The revision refuses when rows exist and the user count
   is not exactly one. The owner is derived from the fact that the installation had one
   candidate; nothing is guessed. `app_settings` (one row) becomes that user's
   `user_settings` row, keyed by `user_id`.
4. Storage keys do not change. They already embed the Application ID, and ownership of
   a payload comes from its registered reference, not from its key (architecture §6.2).

After the Knowledge step, `base/` and the candidate-specific parts of `profiles/` are
import input only. They are no longer read at runtime.

## 5. Delivery order

Each step is its own pull request and brings the focused tests for what it changes, as
`CLAUDE.md` requires. Until step 6 ships, the database admits one user (decision 14),
so no step before it can expose one user's data to another.

1. **Specs and decision records.** Documentation only.
2. **Login, backend:** `users`, `user_sessions`, and the `users_single_user` index;
   `create-user` and `set-password` (`--password-stdin` as well as a prompt); `login`,
   `logout`, `logout-all`, `me`, `change-password`. The other routes do not yet require
   a session, so the Web client keeps working while it has no sign-in screen.
3. **Login, frontend, and enforcement:** the sign-in screen, the auth state, private
   routes, a `401` clearing the auth state and the query cache, sign-out clearing
   per-user browser state; and, in the same change, the session dependency that makes
   every route but sign-in and health answer `401` without a session. Enforcement and
   the screen ship together so `main` never has one without the other.
4. **Per-user Knowledge:** `facts`, `candidate_contexts`, `profile_bindings`
   (architecture §18.2); `import-knowledge`; the journal retired; the Profile
   template/binding split. The riskiest step for fact semantics. `edit_fact` follows it
   (`editable-facts.md` §3).
5. **Ownership and isolation:** `applications.user_id` and `user_settings` with the
   existing installation assigned to its one user (§4); every service resolving through
   the `Actor` (architecture §18.3), every list, count, and duplicate check scoped; the
   per-Application idempotency key; the worker deriving the owner from the Operation's
   Application. The derived isolation guards arrive with what they cover.
6. **Second user enabled:** the cross-user route matrix, the schema ownership guard, and
   the persistence-port guard made complete and blocking in CI; the sign-in rate limit;
   renderer hardening (architecture §18.6); then a migration drops `users_single_user`.
7. **Hosted deployment:** public origin, Host allowlist, HSTS, and the hosting decisions
   in §6.

## 6. Deferred and open items

**Deferred.** Each is out of the delivery order until its condition holds. Its earlier
design is in Git history at `3bf3034` (architecture §18, state-and-use-cases §23); it
returns as a change to the specifications first.

- **Ending an account** (deactivation and anonymization of mutable personal data) —
  when a user other than the operator must be able to leave, or before the product
  opens to people the operator does not know. Its open question returns with it:
  Submissions, the job text they locked, the AI call log, and `fact_events.fact_json`
  keep a candidate's name and contacts, and whether anonymization without erasure is
  acceptable is a legal decision, not a technical one.
- **Per-user AI quota** — when a user exists whose provider spend the operator does not
  want to trust.
- **Fairness between users in the worker's claim order** — when one user's queue is
  seen holding back another's. Until then the claim order stays oldest first.
- **Account events** (an append-only sign-in and password audit) — when the server log
  is not enough to answer who signed in and when.
- **Email verification and reset by email** — only with a decision to open sign-up
  (decision 12).

**Open.**

1. **Numeric limits.** The defaults in architecture §18 are starting values, not
   measured ones.
2. **Hosting.** Where it runs, who terminates TLS, and PostgreSQL and bucket backup are
   the operator's choice and are not specified here; step 7 needs them decided.
