# Claude Instructions — CV Tailor Project

## Purpose
Generate tailored CV versions from a base CV and a job description.

## Always read before starting
- `base/cv_base.md` — source of truth, never modify
- `rules/cv_generation_rules.md` — full process and hard rules
- `examples/cv_example_backend.md` — reference output format

## Workflow

1. If no job description provided — ask for it:
   ```
   Company:
   Role:
   Job description: ...
   ```

2. Run gap analysis — return table: required vs. present vs. missing

3. Offer tone choice and wait for response:
   - **A — Technical depth**
   - **B — Balanced**
   - **C — AI/GenAI focused**

4. Generate tailored CV → save to `outputs/<company>/cv-drafts/cv_<company>_<role>.md`
   - Clean CV only — no notes inside
   - Include front-matter at top:
     ```yaml
     ---
     created: YYYY-MM-DD
     modified: YYYY-MM-DD
     ---
     ```

5. Save tailoring decisions → `outputs/<company>/cv-drafts/cv_<company>_<role>.notes.md`
   - Include front-matter at top:
     ```yaml
     ---
     created: YYYY-MM-DD
     modified: YYYY-MM-DD
     ---
     ```

6. Convert `.md` → `.html` using `resume_base.html` as visual template
   → save as `outputs/<company>/cv-html/cv_<company>_<role>.html`

7. Automatically save job description → `outputs/<company>/job-description/<company>_<role>.md`
   - Use the template format from `jobs/job_description_example.md`
   - Include front-matter at top:
     ```yaml
     ---
     created: YYYY-MM-DD
     modified: YYYY-MM-DD
     ---
     ```

8. Automatically add row to `jobs/status.csv`:
   - Fields: company, role, url, cv_file, status (draft), date_sent (today), notes
   - cv_file field: `outputs/<company>/cv-pdf/cv_<company>_<role>.pdf`

9. Remind user:
   ```bash
   bash print_pdf.sh outputs/<company>/cv-html/cv_<company>_<role>.html
   ```

10. Remind user to:
    - Run through `CHECKLIST.md` before sending
    - Update `jobs/status.csv` status when sent

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
      cv_<company>_<role>.pdf
  archive/
```

## PDF Flow — never break this order
1. `.md` → `.html` (via `resume_base.html` template)
2. `.html` → `.pdf` (via `print_pdf.sh`)
3. Never run `print_pdf.sh` on a `.md` file

## Archive rule
If an output file already exists — move it to `outputs/archive/` before writing the new version.

## Hard Rules
- Never modify `base/cv_base.md`
- Never overwrite output files without archiving first
- Never invent experience, technologies, metrics, or dates
- Never inflate seniority or change title beyond allowed variants
- Never use buzzwords: passionate, ninja, rockstar, dynamic, results-driven
- Only facts from `base/cv_base.md`

## Tone
- Professional, concise, direct
- Backend-oriented when relevant
- No exaggerated claims
- ATS-optimized: job keywords embedded naturally
