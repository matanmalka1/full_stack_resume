# Task: separate secrets from configuration

Repository: `resume_python`, branch `main`. Read this fully before touching anything.

## 0. Authority

This prompt supersedes `CLAUDE.md` and `docs/v2/spec/` where they conflict, for this task
only. The user is moving this project toward a real deployment; the "local only, not
deployed" framing is superseded on that subject. **Do not stop to report that
contradiction.**

Everything here is development material. No data to preserve, no backward compatibility.

**A second agent may be working on `frontend/`. Never edit anything under `frontend/`.**

## 1. The problem

`runtime/config.py` holds 11 `Setting` entries, all read from environment variables. Two
of them now carry credentials:

- `CV_DATABASE_URL` — contains the PostgreSQL password
- `CV_S3_BUCKET` / `CV_S3_ENDPOINT_URL` — plus AWS credentials read by boto3 from the
  ambient environment, which this config never sees

`OPENAI_API_KEY` is read directly from `os.environ` in `runtime/composition.py:164`,
bypassing the config contract entirely.

Three concrete gaps:

1. **No `.env` support.** Every secret must be exported by hand in each shell. This has
   already cost real time: a stale `CV_PROVIDER` and a stale `CV_DATABASE_URL` each
   produced test failures that looked like code defects.
2. **`.gitignore` has no `.env` entry.** A developer who creates one can commit it.
3. **No masking.** A secret can reach logs, `cv workspace status` output, or an error
   message. Note the inverse already bit us: `str(engine.url)` returns `***`, and a test
   fixture handed that masked value on as a real URL (fixed in `7170bef`). Masking must
   happen at the display boundary, never in the value the code uses.

## 2. What to build

**Mark settings as secret.** Add a `secret: bool = False` field to `Setting`. Mark
`database_url` and any credential-bearing setting you add. The flag drives masking; it
does not change how the value is read or used.

**Load `.env`.** Read a `.env` file from the Workspace root, or the repository root when
no Workspace is open. **Precedence: real environment variables win over `.env`** — a
value explicitly exported must not be silently overridden by a file. Parse it yourself;
do not add `python-dotenv` for this (see §4).

**Mask at the display boundary.** Every place that prints or logs a config value must
show `***` for a secret setting. At minimum: `cv workspace status`, any config
reporting in the API, and error messages that echo a setting. The masked form must never
be written back into a variable the code then connects with.

**Add `.env` and `.env.*` to `.gitignore`**, excluding `.env.example`.

**Write `.env.example`** — every setting name with a safe placeholder, committed, and no
real credential in it.

**Route `OPENAI_API_KEY` through the config contract** as a secret setting, so
`composition.py` stops reaching into `os.environ` directly. Preserve the existing
behaviour exactly: the adapter is built only when a key is configured, and the
deterministic workflow must still reach Ready with no key set.

## 3. Non-goals

No secret manager, no vault, no KMS, no encryption at rest. This is file-and-environment
hygiene, nothing more. Do not add auth, users, or tenancy — those are separate tasks.

## 4. Rules

- **You do not run tests.** Hand back commands. You may run `ruff`, `pyright`, `grep`,
  `python -c` imports, and a one-off script probing a single function.
- **Delete what this makes dead** (no shims, no aliases, no `if legacy:` branches).
- **No new dependency** unless you stop and justify it first. `CLAUDE.md` requires a
  concrete reason, and a ~40-line `.env` parser does not need a library.
- **Stop and ask** if masking would change a value the code actually uses, if a setting's
  secret status is ambiguous, or if any acceptance item cannot be honestly ticked.

## 5. Acceptance

1. `.env` is loaded; a real environment variable still wins over it.
2. `.gitignore` covers `.env` and `.env.*` but not `.env.example`.
3. `.env.example` is committed and contains no real credential.
4. `cv workspace status` shows `***` for every secret setting and real values for the
   rest.
5. `grep -rn "os.environ" cv_engine/` shows no direct secret read outside `config.py`.
6. Backend suite still passes at the 339 baseline, with every difference explained.
7. `docs/v2/smoke-run.md` still reaches `preparation_state: ready` offline with
   `OPENAI_API_KEY` unset.
8. `frontend/` untouched.

## 6. Reporting

Never claim completion with "implemented" alone. Report what passed, what failed, what
remains. For each stage: the commits and diffs, the ordered commands each using
`./.venv/bin/python`, the predicted test count with deviations explained, what you
deleted, and anything you could not verify because you did not run it.
