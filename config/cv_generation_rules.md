# CV Generation Rules

Supplements `CLAUDE.md` (process, output paths, hard rules already covered there — not repeated here).

This file defines the **output contract** for `outputs/<company>/cv-drafts/cv_<company>_<role>.md`.
Every rule below is stated so it can be checked mechanically. If a rule cannot be
checked, it does not belong in this file.

---

## Title Rules — Never Break

Do not change the candidate's title to one that overstates seniority or specialization.

Allowed tagline variants (pick exactly one):
- `Full-Stack Developer · Python/FastAPI · React · AI Integrations`
- `Full-Stack Developer · Python/FastAPI · React`
- `Backend-Oriented Full-Stack Developer`
- `Full-Stack Developer · AI Integrations`

Not allowed:
- Senior Full-Stack Developer
- AI Engineer
- Backend Architect
- Lead Developer
- any title implying a seniority level not stated in `base/cv_base.md`

---

## Additional Hard Rules

- Do not claim production experience with tools not in the base CV
- Do not delete backend experience to make room for other content

---

## Fixed Output Skeleton — Never Vary

The structure below is fixed across every draft. Content changes per job; layout does not.

### Document order

1. YAML front-matter
2. `# Matan Malka`
3. Tagline
4. Contact block (2 lines)
5. `---`
6. `## Profile`
7. `---`
8. `## Work Experience`
9. `---`
10. `## Education`
11. `---`
12. `## Skills`
13. `---`
14. `## Languages`

No section may be added, removed, or reordered. `## Projects` is **not** part of the
output skeleton: the Projects section in `base/cv_base.md` is a fact reservoir, not a
CV section.

### Exact line formats

```
---
created: YYYY-MM-DD
modified: YYYY-MM-DD
---

# Matan Malka

Full-Stack Developer · Python/FastAPI · React

Tel Aviv · +972-50-668-8386 · matan1391@gmail.com
[GitHub](https://github.com/matanmalka1) · [LinkedIn](https://www.linkedin.com/in/matanmalka1)
```

- **Tagline**: its own line, plain text, no bold, no heading marker. One of the four
  allowed variants above, copied character for character. It lives in the `.md`,
  not only in the `.html`.
- **Contact block**: exactly two lines, in the order shown, no bullets.
- **Job / education title line**: `### <Title> — <Company/School>, <City>`
- **Date line**: bold, immediately under the title line: `**2025 – 2026**`,
  `**990 hours, 2024 – 2025**`
- **Languages**: one bullet per language, `- <Language> — <Level>`
- **Skills**: a two-column markdown table, header `| Category | Technologies |`.
  Row order may be re-prioritized per job; row content must come from `base/cv_base.md`.
- **Section dividers**: a `---` line between every top-level `##` section, including
  before the first `##`. No divider after the final section.

### Dash rules

Stated as requirements, not as exceptions to a ban.

| Character | Required in | Forbidden in |
|---|---|---|
| Em dash `—` | `### <Title> — <Company>, <City>` lines; `- <Language> — <Level>` lines | everywhere else, including all prose |
| En dash `–` | date ranges (`2025 – 2026`, `2024 – 2025`); digit-to-digit numeric ranges (`3–4`) | prose, outside a numeric or date range |
| Hyphen `-` | normal hyphenation (`Full-Stack`, `role-based`) | as a substitute for a required em/en dash |

"Prose" means the Profile paragraph and all bullet text. Headers, date lines, and the
Languages block are not prose.

Never substitute `·`, `-`, `–`, or a plain comma where an em dash is required.

### Bold

Bold is permitted in exactly one place: the date line under a `###` title.

No inline bold anywhere else. In particular, no bold on technology terms inside bullets
(`**React**`, `**PostgreSQL**`, `**JWT**` are all violations). ATS parses plain text
identically, and inline bold creates a second place for the `.md` and `.html` to drift
apart.

---

## Reference conformance

`config/cv_example_backend.md` is the reference output and must itself satisfy every
rule above. It is the reference, so it cannot be the exception. It must contain no
commentary, no notes, and no trailing example annotations: tailoring commentary belongs
only in `cv_<company>_<role>.notes.md`.