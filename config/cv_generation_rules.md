# CV Generation Rules

Supplements `CLAUDE.md` (process, output paths, hard rules already covered there — not repeated here).

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

## Additional Hard Rules
- Do not claim production experience with tools not in the base CV
- Do not delete backend experience to make room for other content

## Fixed Output Skeleton — Never Vary
The "no em dash" rule in `CLAUDE.md` applies to **prose text only** (Profile
paragraph, Work Experience/Education/Projects bullets). Headers, the Languages
line, and date ranges are not prose — em dash there matches `base/cv_base.md`'s
own native style and is fine. What must stay fixed across every draft is the
*structure*, not a ban on em dash everywhere:

- Name: `# Matan Malka`
- Tagline: plain text, no bold — `Full-Stack Developer · Python/FastAPI · React` (pick the allowed variant per Title Rules above)
- Contact line (one line, no bullets): `Tel Aviv · +972-50-668-8386 · matan1391@gmail.com` followed by a line break, then `[GitHub](https://github.com/matanmalka1) · [LinkedIn](https://www.linkedin.com/in/matanmalka1)`
- Section dividers: `---` between every top-level `##` section, including before the first `##` and after the last one — same as `base/cv_base.md`
- Job/education title lines: `### <Title> — <Company/School>, <City>` — always em dash here, matching `base/cv_base.md` exactly (do not substitute `·`, `-`, `–`, or a plain comma)
- Languages line: one bullet per language, `- <Language> — <Level>`, em dash — matching `base/cv_base.md`'s per-line format (not the condensed single-line `·`-joined variant)
- Prose (Profile paragraph, bullets): never use em dash — use a colon or restructure the sentence, per `CLAUDE.md`
- No inline bold on technology terms inside bullets (matches `base/cv_base.md` style; keep tech keywords in plain text, ATS parses text either way)

`config/cv_example_backend.md` must itself conform to this skeleton — it is the
reference, so it cannot be the exception.
