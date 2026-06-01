# CV Generation Rules

## Input
- Source of truth: `base/cv_base.md`
- Job description: provided inline or from `jobs/<company>_<role>.md`
- Reference output: `examples/cv_example_backend.md`

## Process

1. **Analyze** the job description:
   - Required technologies and tools
   - Responsibilities and seniority level
   - Keywords likely used by ATS

2. **Gap analysis** — return a table before generating:
   | Required by job | Present in base CV | Gap |
   |-----------------|-------------------|-----|

3. **Ask for tone** before generating:
   - **A — Technical depth:** backend, architecture, system design
   - **B — Balanced:** full-stack + product/business sense
   - **C — AI/GenAI focused:** LLM integrations, OpenAI/Anthropic API, prompt engineering

4. **Generate** tailored CV:
   - Rewrite Profile to match the role
   - Reorder Skills table rows — most relevant first
   - Rephrase bullets using job keywords (do not change facts)
   - Keep one page worth of content when possible

5. **Save CV** to `outputs/cv_<company>_<role>.md` — clean CV only, no notes

6. **Save tailoring notes** to `outputs/cv_<company>_<role>.notes.md`:
   ```
   ## Tailoring Notes — <company> <role>
   - Tone chosen: A / B / C
   - Profile: [what changed and why]
   - Skills order: [what moved to top]
   - Bullets: [key rephrasing decisions]
   - Gaps not addressed: [what was missing and left out]
   ```

7. **PDF flow** (remind user):
   - Convert `.md` → `.html` using `resume_base.html` as template
   - Run: `bash print_pdf.sh outputs/cv_<company>_<role>.html`
   - Never run `print_pdf.sh` on a `.md` file

8. **Archive** old versions before overwriting: move to `outputs/archive/`

## Title Rules — Never Break
Do not change the candidate's title to one that overstates seniority or specialization.

Allowed tagline variants:
- `Full-Stack Developer · Python/FastAPI · React · AI Integrations`
- `Full-Stack Developer · Python/FastAPI · React`
- `Backend-Oriented Full-Stack Developer`
- `Full-Stack Developer · AI Integrations`

Not allowed:
- Senior Full-Stack Developer
- AI Engineer
- Backend Architect
- Lead Developer
- (any title implying a seniority level not stated in `base/cv_base.md`)

## Hard Rules — Never Break

- Use only facts from `base/cv_base.md`
- Do not invent: companies, dates, technologies, metrics, achievements
- Do not claim production experience with tools not in the base CV
- Do not inflate seniority
- Do not use buzzwords: passionate, ninja, rockstar, dynamic, results-driven
- Do not modify `base/cv_base.md`
- Do not overwrite existing output files — move old version to `outputs/archive/` first
- Do not delete backend experience to make room for other content
- Do not include tailoring notes inside the CV file

## Output Files
| File | Content |
|------|---------|
| `outputs/cv_<company>_<role>.md` | Clean tailored CV |
| `outputs/cv_<company>_<role>.notes.md` | Tailoring decisions and gaps |
| `outputs/cv_<company>_<role>.html` | HTML for PDF export |
| `outputs/cv_<company>_<role>.pdf` | Final output |

File name format: lowercase, hyphens for spaces.
Example: `outputs/cv_monday_fullstack-developer.md`
