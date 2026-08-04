---
created: 2026-08-03
modified: 2026-08-03
---

# Tailoring notes — CodeValue / Sales Development Representative

## Source override
Content sourced from a separate sales resume PDF the user supplied for this draft
only ("Matan Malka team leader Hebrew.pdf"), not from `base/cv_base.md`. User
instruction: use this source for this CV only, do not merge into base CV or reuse
in other drafts.

## Pipeline deviation
`build_html.py` / `config/cv_generation_rules.md` hard-code a dev-only title
whitelist (`Full-Stack Developer`, `Backend-Oriented Full-Stack Developer`) and a
dev tech-term whitelist for the tagline. Neither fits a sales CV. User chose to
skip `build_html.py --check` and rendering for this draft and format by hand
instead — confirmed via direct question, not assumed. `.md` still follows the
same dash/bold/skeleton conventions as the normal contract (em dash in title/date
lines, en dash in date ranges, no inline bold, no buzzwords) even though the
mechanical validator wasn't run against it.

## Content decisions
- Title used: "Sales Team Leader" (highest role actually held), tagline adds
  "B2B Sales · Key Account Management" for keyword relevance — not validated
  against any whitelist since none exists for this domain.
- GitHub link dropped (not relevant to a sales role); LinkedIn kept.
- Full-Stack Development bootcamp (John Bryce) omitted from Education entirely —
  not relevant to an SDR application and could read as a signal the candidate is
  pursuing a different career track. This is an omission, not a fact change;
  flag if the user wants it included anyway.
- Dates used as stated on the source resume: 2019–2022 (Field Sales Rep) +
  2022–2025 (Team Leader) = 6 years, not the "7 years" mentioned verbally in
  chat. Resume is the written source of truth.

## Gaps not fabricated
- "Quarterly targets" (Must-have) — source resume shows KPI/goal tracking and a
  30% revenue increase, but never frames it as quarterly cadence. Did not invent
  "quarterly."
- "Experience in Software Development / professional services industry"
  (Advantage) — Pcom Solutions' industry isn't stated in the source resume.
  Left out rather than guessed.
- "Excellent interpersonal & communication skills, inbound and outbound" —
  source resume documents negotiation/client relations and outbound field
  activity; no inbound-specific experience is stated.
- **Notable mismatch, not papered over**: the role is described as "primarily
  phone-based, with... only occasional meetings." The candidate's background is
  field sales (in-person meetings, site visits) at Pcom Solutions. This is a
  genuine gap in work style fit, not just a keyword gap — flagged for the user's
  own judgment before applying, not solved by rewording.
