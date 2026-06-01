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

4. Generate tailored CV → save to `outputs/cv_<company>_<role>.md`
   - Clean CV only — no notes inside

5. Save tailoring decisions → `outputs/cv_<company>_<role>.notes.md`

6. Convert `.md` → `.html` using `resume_base.html` as visual template
   → save as `outputs/cv_<company>_<role>.html`

7. Remind user:
   ```bash
   bash print_pdf.sh outputs/cv_<company>_<role>.html
   ```

8. Remind user to:
   - Save job description to `jobs/<company>_<role>.md`
   - Add row to `jobs/status.csv`
   - Run through `CHECKLIST.md` before sending

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
