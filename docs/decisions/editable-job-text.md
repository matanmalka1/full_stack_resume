# Decision: the job text is an editable field, locked by the first Submission

Status: implemented (2026-10-05). The specifications describe this model and are
authoritative; this record keeps why and what was removed.

## 1. Why

The job posting was stored as immutable, versioned JobSnapshots: a payload file per
version in the object store, a metadata row with its own hashes, immutability triggers,
a history view with text comparison, and a "new snapshot" command for every change.

What the product needs from the posting is narrower:

1. **Keep the text.** Postings vanish from the web; the candidate needs to see what they
   applied to when an interview call comes weeks later.
2. **Know which text an analysis read.** Analysis quotes requirements from the text and
   the engine attests every quote against it. That needs the hash of the text the
   analysis read, not a version history.
3. **Keep what was sent tied to its posting.** After a Submission the text it was sent
   for must not change.

Versioning served none of these beyond what a hash and a lock give. A saved posting
rarely changes, and when it does the current text is the one that matters. In a
single-candidate tool the immutability triggers on the posting protected the user from
correcting their own paste. The separate payload file, its checksum, and its
reconciliation guarded a few tens of kilobytes of text a column holds.

## 2. The model

- `applications` carries `job_text`, `job_text_hash` (SHA-256 of the exact text),
  `job_normalized_hash` (duplicate detection), `source_url`, and `job_text_updated_at`.
- `update_job_text` edits it in place, guarded by `expected_job_text_hash` and audited.
- A JobAnalysis records the `job_text_hash` it read. After an edit, earlier analyses stay
  on record and are no longer of the Application's text: Analyze becomes available and
  the document reads `DOCUMENT_ON_OLDER_ANALYSIS`. A document whose analysis read an
  earlier text cannot be drafted (`JOB_TEXT_CHANGED`), since that text is gone.
- The first Submission, internal or external, locks the text. The store refuses the
  edit under the Application row lock that `submit_application` also takes, and the
  trigger `lock_submitted_job_text` refuses it in the database. A Submission records the
  `job_text_hash` it was sent for.

Specified in `product-spec.md` §8 and §16, `state-and-use-cases.md` §2, §8, §9, §12 and
§18, and `architecture.md` §6.

## 3. What was removed

- The `job_snapshots` table, the `snapshots/` payload layout, and the payload reads.
- `create_job_snapshot`, `GET/POST /applications/{id}/job-snapshots`, the snapshot
  history view and its text comparison, and the duplicate-snapshot 409.
- `job_snapshot_id` on analyses, Operations sources, the document content binding
  (`DraftDocument` schema 1.3 carries `job_text_hash`), and Submissions.

Requirement identity is still the normalized hash of the posting's text; its payload
keys are now named `job_text` and `identity_version` (no ids needed to stay stable).

## 4. What was not built

- **A copy of the text in each Submission.** The lock makes it unnecessary: a
  Submission's `job_text_hash` always names text the Application still holds.
- **Keeping earlier texts.** An edit before submission discards the earlier text. An
  analysis of it stays readable but cannot be drafted from.

There was no data to migrate: the database starts empty (CLAUDE.md), and the baseline
revision was changed in place.
