# CV Tailor Project

Tailored CV versions generated from a base CV using Claude Code or Codex.
No application code: the project is a set of markdown instruction files plus two
bash scripts.

## Structure

```
├── CLAUDE.md                          # Agent instructions (auto-loaded by Claude Code)
├── agents.md                          # Mirror of CLAUDE.md for Codex
├── README.md
├── CHECKLIST.md                       # Pre-send review checklist
├── build_html.py                      # Validate a draft and render it to HTML
├── check_status.py                    # Reconcile status.csv against disk
├── print_pdf.sh                       # Export HTML → PDF via Chrome headless
├── base/
│   ├── cv_base.md                     # Source of truth — never edited for a specific job
│   └── cv-pdf/                        # Untailored PDF of the base CV
├── config/
│   ├── cv_generation_rules.md         # Output contract: title rules, fixed skeleton
│   ├── cv_example_backend.md          # Reference output (backend tone)
│   ├── cv_example_backend.notes.md    # Reference notes file
│   ├── job_description_example.md     # Template for saving job descriptions
│   └── resume_base.html               # HTML template for PDF export
├── docs/
├── jobs/
│   └── status.csv                     # Application tracking
└── outputs/
    ├── <company>/
    │   ├── job-description/<company>_<role>.md
    │   ├── cv-drafts/cv_<company>_<role>.md         # Clean tailored CV
    │   ├── cv-drafts/cv_<company>_<role>.notes.md   # Tailoring decisions (never in the CV)
    │   ├── cv-html/cv_<company>_<role>.html         # HTML for PDF export
    │   └── cv-pdf/<role>/Matan Malka - Full Stack Developer.pdf
    └── archive/                       # Previous versions, moved here before overwrite
```

## Usage

Open Claude Code or Codex in this directory and paste a job description:

```
Company: monday.com
Role: Full-Stack Developer
Job description: ...
```

The agent will:

1. Check `jobs/status.csv` for an existing draft for the same company and a similar role
2. Run gap analysis (required vs. present vs. missing), including `Situational Skills`
3. Ask for tone (A technical / B balanced / C AI-focused)
4. Write `outputs/monday/cv-drafts/cv_monday_full-stack-developer.md`
5. Write `outputs/monday/cv-drafts/cv_monday_full-stack-developer.notes.md`
6. Run `build_html.py --check` on the draft and fix it until it passes
7. Run `build_html.py` to render `outputs/monday/cv-html/cv_monday_full-stack-developer.html`
8. Save the job description under `outputs/monday/job-description/`
9. Add a row to `jobs/status.csv` with `status=draft` and an empty `date_sent`
10. Run `print_pdf.sh` and report the PDF path
11. Run `check_status.py` and resolve anything it reports

## Validate a draft

```bash
python3 build_html.py --check outputs/<company>/cv-drafts/cv_<company>_<role>.md
```

## Render to HTML

```bash
python3 build_html.py outputs/<company>/cv-drafts/cv_<company>_<role>.md
```

The builder is the only way HTML is produced. It fails loudly on any violation of the
output contract and writes nothing. Never hand-edit a generated `.html`.

## Export to PDF

```bash
bash print_pdf.sh outputs/<company>/cv-html/cv_<company>_<role>.html
```

`print_pdf.sh` writes to `outputs/<company>/cv-pdf/<role>/Matan Malka - Full Stack Developer.pdf`.
The filename is fixed because that is what a recruiter sees. The `<role>` folder is what
keeps two live roles at the same company from overwriting each other. An existing PDF at
that path is moved to `outputs/archive/` first, never replaced in place.

## Check tracking

```bash
python3 check_status.py
```

**Flow:** `.md` → `.html` (`build_html.py` + `config/resume_base.html`) → `.pdf`
Never export a PDF directly from a `.md` file.

## Rules

- `base/cv_base.md` is never modified
- Output files are archived before overwrite, never silently deleted
- No invented experience, technologies, metrics, or dates
- Title variants are restricted: no seniority inflation
- `Situational Skills` items are pulled in only when a job explicitly requires that item

The full output contract lives in `config/cv_generation_rules.md`.