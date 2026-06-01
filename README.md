# CV Tailor Project

Tailored CV versions generated from a base CV using Claude Code.

## Structure

```
├── CLAUDE.md                          # Claude instructions (auto-loaded)
├── README.md
├── CHECKLIST.md                       # Pre-send review checklist
├── resume_base.html                   # HTML template for PDF export
├── print_pdf.sh                       # Export HTML → PDF via Chrome headless
├── base/
│   └── cv_base.md                     # Source of truth — never edit for a specific job
├── rules/
│   └── cv_generation_rules.md         # Generation process, title rules, hard constraints
├── examples/
│   └── cv_example_backend.md          # Reference output (backend tone)
├── jobs/
│   ├── job_description_example.md     # Template for saving job descriptions
│   └── status.csv                     # Application tracking
└── outputs/
    ├── cv_<company>_<role>.md         # Clean tailored CV
    ├── cv_<company>_<role>.notes.md   # Tailoring decisions (not in CV)
    ├── cv_<company>_<role>.html       # HTML for PDF export
    ├── cv_<company>_<role>.pdf        # Final output
    └── archive/                       # Old versions before overwrite
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
3. Generate `outputs/cv_monday_fullstack-developer.md`
4. Save notes to `outputs/cv_monday_fullstack-developer.notes.md`
5. Convert to `outputs/cv_monday_fullstack-developer.html`

## Export to PDF

```bash
bash print_pdf.sh outputs/cv_<company>_<role>.html
```

**Flow:** `.md` → `.html` (resume_base.html as template) → `.pdf`

## Rules
- `base/cv_base.md` is never modified
- Output files are archived before overwrite, never silently deleted
- No invented experience, technologies, or metrics
- Title variants restricted — no seniority inflation
