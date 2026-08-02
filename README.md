# CV Tailor Project

Tailored CV versions generated from a base CV using Claude Code.

## Structure

```
├── CLAUDE.md                          # Claude instructions (auto-loaded)
├── agents.md                          # Mirror of CLAUDE.md for Codex
├── README.md
├── CHECKLIST.md                       # Pre-send review checklist
├── check_cv.sh                        # Lint draft for buzzwords/em dashes
├── print_pdf.sh                       # Export HTML → PDF via Chrome headless
├── base/
│   └── cv_base.md                     # Source of truth — never edit for a specific job
├── config/
│   ├── cv_generation_rules.md         # Generation process, title rules, hard constraints
│   ├── cv_example_backend.md          # Reference output (backend tone)
│   ├── job_description_example.md     # Template for saving job descriptions
│   └── resume_base.html               # HTML template for PDF export
├── jobs/
│   └── status.csv                     # Application tracking
└── outputs/
    └── <company>/
        ├── job-description/<company>_<role>.md
        ├── cv-drafts/cv_<company>_<role>.md         # Clean tailored CV
        ├── cv-drafts/cv_<company>_<role>.notes.md   # Tailoring decisions (not in CV)
        ├── cv-html/cv_<company>_<role>.html         # HTML for PDF export
        └── cv-pdf/cv_<company>_<role>.pdf           # Final output
    outputs/archive/                   # Old versions before overwrite
```

## Usage

Open Claude Code in this directory and paste a job description:

```
Company: monday.com
Role: Full-Stack Developer
Job description: ...
```

Claude will:
1. Run gap analysis
2. Ask for tone (A / B / C)
3. Generate `outputs/monday/cv-drafts/cv_monday_fullstack-developer.md`
4. Save notes to `outputs/monday/cv-drafts/cv_monday_fullstack-developer.notes.md`
5. Convert to `outputs/monday/cv-html/cv_monday_fullstack-developer.html`

## Export to PDF

```bash
bash print_pdf.sh outputs/<company>/cv-html/cv_<company>_<role>.html
```

**Flow:** `.md` → `.html` (`config/resume_base.html` as template) → `.pdf`

## Rules
- `base/cv_base.md` is never modified
- Output files are archived before overwrite, never silently deleted
- No invented experience, technologies, or metrics
- Title variants restricted — no seniority inflation
