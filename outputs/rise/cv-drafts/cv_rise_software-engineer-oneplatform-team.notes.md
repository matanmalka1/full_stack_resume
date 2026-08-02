---
created: 2026-08-02
modified: 2026-08-02
---

# Tailoring Notes — Rise, Software Engineer (OnePlatform Team)

## Tone
A — Technical depth.

## Gap analysis

| Required | Status | Notes |
|---|---|---|
| General-purpose language (Python/JS) | Present | Python, JS/TS |
| Frontend framework (React) | Present | React |
| Structured config (YAML/JSON) | Present | Pulled from Situational Skills — added to base CV this session, confirmed real (PH.Digital) |
| Git + PR workflow | Present | |
| GCP / AWS | Partial | AWS EC2 only, no GCP — not fabricated |
| HTML/CSS (frontend advantage) | Present | Pulled from Situational Skills — real (PH.Digital, React work) |
| Windows/C++/C#, registry, WinAPI (advantage) | Missing | Not in base CV, not added |
| Ad-tech terminology (advantage) | Missing | Not in base CV, not added |
| Agentic systems | Present | Pulled AI-assisted development from Situational Skills — JD explicitly says "Utilize, maintain & handle Agentic systems" |
| Kubernetes | Missing | Not in base CV, not added |
| AI Security / Prompt Injection / Data Leakage | Missing | Not in base CV, not added |
| Cybersecurity / DLP | Missing | Not in base CV, not added |
| Testing/debugging | Present | Pulled pytest from Situational Skills — JD says "analytical and problem-solving skills to resolve technical issues"; not a literal "testing" requirement, borderline call, user confirmed include |

## Base CV change
Added new Situational Skills line to `base/cv_base.md`: "Structured configuration: YAML/JSON config files used to drive application behavior at PH.Digital." — confirmed by user as real, PH.Digital-sourced. This is a permanent addition to the base CV (not just this draft).

## Decisions
- Pulled in YAML/JSON config, HTML5/CSS3, Testing (pytest), and AI-assisted development from Situational Skills — JD requires/implies all four.
- Did not add GCP, Windows/C++/C#, ad-tech terms, Kubernetes, AI security, or DLP — no real experience, would be fabrication.
- Kept title tagline "Full-Stack Developer · Python/FastAPI · React" — no seniority claim, matches allowed variants.
- Reworked Profile to lead with role fit (full-stack ownership, automation, ticket-driven collaboration) instead of YAML/JSON as the headline — user flagged config wasn't the main point of this job; content trimmed after first PDF export ran to 2 pages (overflow got clipped by print CSS), kept to 4 bullets to stay at 1 page after adding testing/agentic content.
- Removed "agentic coding tools" from Skills — user flagged it oversold as Agent-building experience when it's actually AI coding assistant usage (Cursor/Copilot). Kept the honest version only in the Work Experience bullet ("used AI coding assistants ... with critical review of AI-generated code before merging").
- Added GenAI/OpenAI/LLM mention to Profile opening line — real strength (base CV Generative AI skills + GenAI education project), was missing despite being relevant to this JD's "Agentic systems" duty.
- Languages row: changed separator from "-" to "·" — user reported garbled/corrupted text specifically on that line in the exported PDF. "·" is used elsewhere in this same template (tagline, contacts line) without issue, so switched for consistency; likely a font-glyph/timing issue with the plain hyphen in this Chrome print-to-pdf pipeline.
