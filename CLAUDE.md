# Claude Instructions — CV Tailor Project

## Purpose
Generate tailored CV versions from a base CV and a job description.

## Always read before starting
- `base/cv_base.md` — source of truth, never modify
- `config/cv_generation_rules.md` — the output contract: title rules, fixed skeleton, dash and bold rules. Binding. Where this file and the contract disagree, the contract wins.
- `config/cv_example_backend.md` — reference output format

## Workflow

1. If no job description provided — ask for it:
   ```
   Company:
   Role:
   Job description: ...
   ```

2. Check `jobs/status.csv` for an existing row with the same company + a similar role.
   - If found: tell the user, show its status/date, and ask whether this is an update to that draft or a genuinely new role before continuing.

3. Run gap analysis — return table: required vs. present vs. missing
   - Check both the main CV content and the `Situational Skills` section of `base/cv_base.md`.
   - If a job requirement matches a Situational Skills item, mark it as available (not a gap) and note in the tailoring notes that it was pulled from Situational Skills.
   - Do not include Situational Skills items by default — only when the job explicitly requires that specific item.

4. Offer tone choice and wait for response:
   - **A — Technical depth**
   - **B — Balanced**
   - **C — AI/GenAI focused**

5. Generate tailored CV → save to `outputs/<company>/cv-drafts/cv_<company>_<role>.md`
   - Clean CV only — no notes inside
   - Include front-matter at top:
     ```yaml
     ---
     created: YYYY-MM-DD
     modified: YYYY-MM-DD
     ---
     ```

6. Save tailoring decisions → `outputs/<company>/cv-drafts/cv_<company>_<role>.notes.md`
   - Include front-matter at top:
     ```yaml
     ---
     created: YYYY-MM-DD
     modified: YYYY-MM-DD
     ---
     ```

7. Run `python3 build_html.py --check outputs/<company>/cv-drafts/cv_<company>_<role>.md`
   - Validates the draft against the output contract in `config/cv_generation_rules.md`.
   - Fix the draft and re-run until it passes. Never edit the generated `.html` to work around a failure: the `.md` is the source of truth.

8. Run `python3 build_html.py outputs/<company>/cv-drafts/cv_<company>_<role>.md`
   - Renders `.md` → `.html` through `config/resume_base.html` and writes
     `outputs/<company>/cv-html/cv_<company>_<role>.html`.
   - Never hand-write or hand-edit the `.html`.

9. Automatically save job description → `outputs/<company>/job-description/<company>_<role>.md`
   - Use the template format from `config/job_description_example.md`
   - Include front-matter at top:
     ```yaml
     ---
     created: YYYY-MM-DD
     modified: YYYY-MM-DD
     ---
     ```

10. Automatically add row to `jobs/status.csv`:
    - Fields: company, role, url, cv_file, status (draft), date_created (today), date_sent (leave empty), notes
    - cv_file field: `outputs/<company>/cv-pdf/<role>/Matan Malka - Full Stack Developer.pdf`. The filename is fixed because that is what a recruiter sees; the `<role>` folder is what keeps two roles at the same company apart. `print_pdf.sh` prints this exact path on success: copy it, do not retype it.
    - `date_sent` only gets filled in when the user confirms the application was actually sent (step 12) — never at draft time.

11. Run `bash print_pdf.sh outputs/<company>/cv-html/cv_<company>_<role>.html` directly (local, reversible — no need to ask first). Report the resulting PDF path to the user.

11a. Run `python3 check_status.py`. It reconciles `jobs/status.csv` against disk: missing files, drafts with no row, duplicate unresolved rows. Fix anything it reports before continuing.

12. Remind user to:
    - Run through `CHECKLIST.md` before sending
    - When sent: update `jobs/status.csv` — set `status` to `sent` and fill in `date_sent`

## Output folder structure
Each company gets its own subfolder under `outputs/`, split by output type:
```
outputs/
  <company>/
    job-description/
      <company>_<role>.md          ← job description
    cv-drafts/
      cv_<company>_<role>.md
      cv_<company>_<role>.notes.md
    cv-html/
      cv_<company>_<role>.html
    cv-pdf/
      <role>/
        Matan Malka - Full Stack Developer.pdf   ← fixed filename from print_pdf.sh
  archive/
```

## PDF Flow — never break this order
1. `.md` → `.html` (via `build_html.py`, which renders `config/resume_base.html`)
2. `.html` → `.pdf` (via `print_pdf.sh`)
3. Never run `print_pdf.sh` on a `.md` file
4. Never edit the `.html` by hand. It is generated output: change the `.md` and re-run `build_html.py`

## Archive rule
If an output file already exists — move it to `outputs/archive/` before writing the new version.
- This applies even when the new draft gets a different filename (e.g. a second draft for the same company+role with a different slug). If `jobs/status.csv` already has an unresolved (`status` != `sent`) row for the same company + a similar role, do not create a second live draft — resolve step 2 first (ask the user whether to update the existing draft in place or archive it before creating a new one).

## Hard Rules
- Never modify `base/cv_base.md`
- Never overwrite output files without archiving first
- Never invent experience, technologies, metrics, or dates
- Never inflate seniority or change title beyond allowed variants
- Never use buzzwords: passionate, ninja, rockstar, dynamic, results-driven
- Only facts from `base/cv_base.md`, including its `Situational Skills` section when job-relevant
- Never include Situational Skills items unless the job description explicitly requires that specific item

## Tone
- Professional, concise, direct
- Backend-oriented when relevant
- No exaggerated claims
- ATS-optimized: job keywords embedded naturally
- Formatting, dash placement, and bold: see `config/cv_generation_rules.md`. Do not restate those rules here.