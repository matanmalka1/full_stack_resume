---
created: 2026-08-02
modified: 2026-08-02
---

# Tailoring Notes — Reference Example / Backend Developer

This file is the reference format for `cv_<company>_<role>.notes.md`.
It pairs with `config/cv_example_backend.md`: every draft produces both files,
and all tailoring commentary lives here, never inside the CV.

## Tone
A — Technical depth.

## Title
Used `Backend-Oriented Full-Stack Developer` (allowed variant per
`config/cv_generation_rules.md`) since the role is backend-focused.

## Gap analysis summary

| Requirement | Level | Status |
|---|---|---|
| Python backend framework | Must | Present — FastAPI, Flask |
| Relational database | Must | Present — PostgreSQL, SQLAlchemy |
| REST API design | Must | Present |
| Authentication | Must | Present — JWT |
| CI/CD | Should | Present — GitHub Actions |
| Containerization / cloud | Should | Present — Docker, AWS EC2 |
| Message queues | Advantage | Missing — not in base CV, not fabricated |

## Situational Skills pulled in
None. No requirement in this reference job explicitly called for a
`Situational Skills` item, so none were added.

## Not included
- Message queues and caching layers: not present in `base/cv_base.md` or its
  `Situational Skills` section. Left as a gap rather than invented.
- Projects section: `base/cv_base.md` keeps it as a fact reservoir. It is not part
  of the output skeleton and is not rendered into the CV.

## Changes from base CV
- Skills table rows reordered: `Databases & SQL` and `Tools & Cloud` moved above
  `Frontend` and `Generative AI` to match backend emphasis. No row renamed, no row
  deleted.
- Work Experience bullets reordered so the PostgreSQL / business logic / JWT bullet
  leads. Bullet wording is unchanged from `base/cv_base.md`.
- Profile rewritten to foreground backend ownership and CI/CD. Every claim in it maps
  to an existing bullet in `base/cv_base.md`.

## Fidelity check
Every line in the CV traces to `base/cv_base.md`. Nothing was added, no metric was
extended with explanatory clauses, and no tool was named that does not appear in the
base CV.
