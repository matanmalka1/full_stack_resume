# Multi-Track CV System v1 Upgrade Handoff

Status: **Binding product and implementation specification**  
Primary language: English  
Hebrew and RTL examples remain in their original language where useful  
Repository: `resume_python`

## תקציר מנהלים בעברית

הפרויקט הקיים מפיק קורות חיים מותאמים למשרות Development מתוך מקור אמת אחד,
תיאור משרה וכללי Markdown קשיחים. הוא בודק כפילויות, מבצע gap analysis, יוצר
טיוטת CV והערות, מאמת את המבנה, מפיק HTML ו-PDF, שומר את תיאור המשרה ומעדכן
מעקב ב-CSV. המערכת אמינה יחסית למסלול Development, אך החוזים, הכותרות, מבנה
המסמך, שם ה-PDF והצ'קליסט קשיחים לעולם הפיתוח.

המטרה ב-v1 היא להפוך את הפרויקט למנוע רב-מסלולי אמין עבור Development, Sales
ו-Tech Sales, בלי לבנות עדיין Web UI. מקור האמת יפוצל לקבצים מודולריים, כאשר כל
עובדה נשמרת פעם אחת בלבד. Profiles יקבעו רלוונטיות ומשקל, ו-Rendering Rules
יקבעו כיצד להציג את העובדות. מסלול Sales יתמוך באנגלית ובעברית, כולל RTL מלא,
מבנה דינמי ותתי-פרופילים שונים.

המערכת תסווג אוטומטית Track, Profile ו-Emphasis, תעריך Fit ותציג פערים. היא
תשתמש רק בעובדות מאומתות ותעצור טענות שאינן מקושרות למקור האמת. תהליך ברירת
המחדל יהיה: טיוטה, validation, review של המשתמש, אישור, HTML, PDF ומעקב. מצב
fast mode יוכל לדלג על עצירת האישור, אך לעולם לא על validation.

מצב ההגשות והיסטוריית הסטטוסים יעברו מ-CSV ל-SQLite; מקורות האמת, Profiles
וכללי ההפקה יישארו בקבצי Markdown/YAML מנוהלי Git. migration חד-פעמי ישמור
snapshot מלא, את כל התוצרים ההיסטוריים ואת משמעות ההגשות הקיימות. `ready`
יינתן רק לאחר בדיקות תוכן, מבנה, PDF, חילוץ טקסט ל-ATS, קישורים ותקינות חזותית.

המנדט לסוכן המיישם הוא:

`Review -> Plan -> Implement -> Test -> Migrate -> Verify`

ממשיכים כברירת מחדל. עוצרים רק במקרה של blocker, סתירה לא פתורה, צורך בשינוי
סמנטי, סיכון לאובדן מידע או כשל בטיחות migration. אין לשנות החלטות מוצר בשקט.

---

## 1. Authority and interpretation

This file is the source of truth for the v1 upgrade. Chat history is context only.

The following distinctions are mandatory:

- **Binding product decisions** define observable behavior and may not be changed
  silently.
- **Technical design baselines** may be adjusted when the replacement preserves the
  same product behavior, safety, data, and acceptance criteria.
- **Out-of-scope items** must not expand v1 unless they are strictly necessary to
  satisfy a v1 requirement.

If an implementation concern requires a semantic product change, the implementing
agent must stop, explain the conflict and its consequences, and request a decision.
Internal choices such as class names, module boundaries, and repository implementation
details do not require approval when behavior remains unchanged.

## 2. Current project: what exists today

### 2.1 Purpose and operating model

The repository currently tailors CVs from a base CV and a job description. It is not a
web application. It is an agent-driven, file-based workflow with Python and Bash
scripts.

The current intended flow is:

1. Receive company, role, URL, and job description.
2. Check `jobs/status.csv` for an unresolved application for the same company and a
   similar role.
3. Compare the job requirements with `base/cv_base.md`, including conditional
   `Situational Skills`.
4. Present a gap analysis.
5. Ask for a Development-oriented tone: technical, balanced, or AI/GenAI.
6. Generate a clean Markdown CV and a separate tailoring notes file.
7. Validate the CV with `build_html.py --check`.
8. Render Markdown to HTML with `build_html.py` and `config/resume_base.html`.
9. Save an immutable-at-the-time job-description Markdown file.
10. Add a `draft` row to `jobs/status.csv`.
11. Generate PDF with `print_pdf.sh`.
12. Reconcile tracking and disk state with `check_status.py`.
13. Archive existing output files before replacing them.

### 2.2 Current important files

- `base/cv_base.md`: current Development-oriented source of truth. Existing
  instructions say never to modify it during normal tailoring.
- `config/cv_generation_rules.md`: mechanically oriented Development CV output
  contract.
- `config/cv_example_backend.md`: Development reference output.
- `config/resume_base.html`: shared HTML template.
- `build_html.py`: parser, validator, and Markdown-to-HTML renderer.
- `print_pdf.sh`: HTML-to-PDF flow through headless Chrome.
- `jobs/status.csv`: one-row-per-application tracking.
- `check_status.py`: validates CSV schema, artifact existence, orphan drafts,
  unresolved duplicates, and `sent` date consistency.
- `outputs/<company>/...`: saved job descriptions, drafts, notes, HTML, and PDFs.
- `outputs/archive/`: superseded output versions.
- `CHECKLIST.md`: current Development-oriented pre-send checklist.
- `CLAUDE.md` and the repository agent instructions: current workflow contract.

### 2.3 Current Development contract

The current validator has Development-specific behavior embedded directly in Python:

- Allowed base titles are only `Full-Stack Developer` and
  `Backend-Oriented Full-Stack Developer`.
- Headline terms are a hardcoded technology whitelist.
- The output skeleton is fixed to Profile, Work Experience, Education, Skills, and
  Languages in one exact order.
- Markdown dash and bold rules are enforced globally.
- Contact layout assumes the Development CV pattern.
- The recruiter-facing PDF filename is fixed to
  `Matan Malka - Full Stack Developer.pdf`.
- The checklist contains Development-specific checks.

These rules should remain supported for Development unless the new Development schema
intentionally replaces them without weakening factual safety. They must not be reused
unchanged for Sales.

### 2.4 Existing Sales exception that exposes the limitation

An existing CodeValue Sales Development Representative application was produced outside
the normal pipeline:

- It used a separate, one-time sales resume PDF rather than `base/cv_base.md`.
- The Development-only `build_html.py` contract was skipped.
- Markdown and HTML were built manually while imitating the existing style.
- The PDF was named `Matan Malka - Sales Team Leader.pdf`.
- The exception and factual gaps were documented in its notes file.

This artifact must be preserved during migration. It is historical evidence, not a
template for the new architecture.

### 2.5 Known current factual conflicts to resolve during migration

The current files are not fully aligned with the canonical decisions in this spec:

- `base/cv_base.md` currently says the Sales team had 3-4 representatives. The newly
  confirmed canonical fact is **2-3 Sales representatives**.
- `base/cv_base.md` currently says `Grew team revenue 30% YoY`. This is not canonical.
  The confirmed claim is approximately **30% improvement in team performance and Sales
  revenue over the full management period**, not every year.
- The one-off CodeValue CV shows 2019-2022 and 2022-2025 role dates. The canonical dates
  are March 2019-August 2020 and August 2020-January 2025.

Do not silently copy the stale versions into the new fact store. The migration must use
the canonical facts in Section 7 and retain the old artifacts unchanged as historical
outputs.

## 3. Target product and v1 goal

### 3.1 Product direction

The target is a multi-track CV engine that supports:

- Development
- Sales
- Tech Sales, combining independently verified Sales and Development experience

The near-term product remains agent + files + CLI. A future Web application will sit on
top of the same engine; the engine must not be rewritten for the UI.

The future UI is expected to support job input, Track/Profile selection, language and
emphasis controls, gap analysis, review and approval, CV/PDF generation, decision-record
inspection, application tracking, and artifact history. Building this UI is out of v1.

### 3.2 v1 Definition of Done

> A job enters the system; the system classifies it and evaluates fit; selects only
> verified facts; creates a tailored Hebrew or English draft; validates it; produces a
> valid and ATS-readable PDF after the required approval flow; and stores the
> application and artifact version in SQLite.

This flow must work reliably for Development, Sales, and Tech Sales.

## 4. Core architecture principles

The following principles are binding:

1. `One fact -> one canonical location -> many profiles may reference it.`
2. `Facts -> Profiles -> Rendering Rules` are separate layers.
3. `Version-controlled knowledge in files; mutable application state in SQLite.`
4. `One job analysis -> one canonical fact set -> multiple application artifacts.`
5. `New fact -> pending by default -> explicit confirmation -> canonical.`
6. `Target-role titles are allowed in the resume headline; historical job titles must
   remain factual and canonical.`
7. `Job description by default -> external research only on explicit user request.`
8. `Provider-agnostic core -> task-based AI interface -> provider-specific adapters.`
9. The model proposes; deterministic code and canonical facts validate.
10. `Preserve historical data and outputs, not legacy architecture.`
11. `Preserve meaningful milestones, not every transient draft.`
12. Every submitted artifact is immutable.
13. Every approved CV version has a reproducible decision record.
14. `Proceed by default; stop only for blockers, semantic deviations, unresolved
    ambiguity, or migration safety failures.`

## 5. Proposed repository organization

The exact internal module structure is a technical design choice, but the conceptual
separation below is required:

```text
base/
  common.md
  sales.md
  development.md
  situational_skills.md

profiles/
  development.yaml
  sales/
    field-sales.yaml
    account-manager.yaml
    key-account-manager.yaml
    sdr-bdr.yaml
    account-executive.yaml
    business-development.yaml
    sales-management.yaml
    tech-sales.yaml

rendering/
  rules/
    development.yaml
    sales.yaml
  templates/
    development_ltr.html.j2
    sales_ltr.html.j2
    sales_rtl.html.j2

ai/
  contracts/
  prompts/
  providers/

data/
  applications.sqlite3

artifacts/
  ...

docs/
  v1-upgrade-handoff.md
```

The implementation may preserve `outputs/` rather than introduce `artifacts/` if that
is safer, but all paths and references must be normalized, versioned, and migration-safe.

## 6. Fact model and lifecycle

### 6.1 Modular canonical sources

- `common.md`: contact information, languages, education, logistics, and shared career
  facts.
- `sales.md`: full canonical Pcom Solutions Sales history and verified Sales facts.
- `development.md`: professional Development history, projects, and technical skills.
- `situational_skills.md`: verified facts that may be used only when a job explicitly
  requires them.

Tech Sales must not duplicate facts. Its Profile may select from both `sales.md` and
`development.md` and apply different weights.

### 6.2 Fact properties

Each usable fact needs a stable ID and enough metadata to support validation and audit.
The implementation should model at least:

- `fact_id`
- canonical content or structured fields
- canonical source file
- tags
- verification status
- source/provenance
- confirmation date
- effective or event dates where relevant
- replacement/supersession reference where relevant
- language-neutral meaning

Useful tags include:

- `sales`
- `development`
- `leadership`
- `new-business`
- `account-management`
- `technical`
- `tech-sales`
- `verified-quantitative`
- `verified-qualitative`
- `situational`

Tags influence selection and weighting. They do not define duplicate storage locations.

### 6.3 Lifecycle

- New information is `pending_fact` by default.
- A pending fact may be used only in the active conversation or tailoring context.
- Explicit user language such as "confirmed", "this is correct", "set this", or
  "add this to the source of truth" promotes the fact directly to canonical.
- Ambiguous facts, conflicts, dates, numbers, tools, and job titles require resolution
  before replacement.
- When a fact replaces another fact, preserve the old version and the replacement link.

### 6.4 Manual editing and claims

Manual editing of a draft is fully allowed.

The validation flow must distinguish:

- Wording-only changes that still express linked facts.
- `derived_statement` text reasonably inferred from facts without creating a new
  measurable claim.
- `unlinked_claim` or `pending_fact` content containing an unsupported factual change.

Before approval:

`manual edits -> claim extraction -> fact linkage -> unsupported-claim check -> approval`

An approved or fast-mode artifact may not contain an unresolved unsupported factual
claim.

## 7. Canonical Sales source of truth for v1

This section records the confirmed Sales facts that must be migrated into `base/sales.md`
and, where shared, `base/common.md`. Do not reinterpret approximate values as exact.

### 7.1 Employer and official role history

Employer: **Pcom Solutions**  
Employment type: Full-time  
Location: Tel Aviv District  
Work mode: Office and field according to role requirements  
Sales territory: Nationwide, Israel

Canonical roles:

1. `Field Sales Representative (B2B)`
   - March 2019 to August 2020
   - Approximately 1.5 years
2. `Team Leader / Sales Supervisor (B2B)`
   - August 2020 to January 2025
   - Approximately 4 years and 6 months

August 2020 is the transition month and may appear in both month-level ranges.

### 7.2 Company activity and customers

- Pcom Solutions was an import/export and wholesale company.
- Its primary activity was supplying and selling mobile devices to businesses in Israel.
- B2B customers included business owners, procurement managers, stores, chains,
  companies, and institutions.
- Sales activity was not restricted to one customer industry.
- The candidate handled both new-customer acquisition and an existing account portfolio.
- Work included field Sales, quotations, and tenders.

### 7.3 Full Sales cycle

Verified activities include:

- Prospecting through cold leads, proactive calls, field activity, referrals, customer
  databases, business relationships, and tenders.
- Initial outreach by phone, email, WhatsApp, physical meetings, and business visits.
- Needs discovery covering quantities, budget, device types, delivery timing, and
  payment terms.
- Independently preparing quotations, matching price and quantity, checking inventory,
  and reviewing commercial terms.
- Negotiating price, credit, payment terms, quantity, delivery, and discounts.
- Closing deals and handing orders into execution.
- Post-Sales follow-through across inventory, delivery, billing, collection, and order
  issues.
- Ongoing account management, repeat orders, retention, upsell, and cross-sell.

### 7.4 Quantitative verified facts

- Managed approximately **40-50 recurring customers**, in addition to occasional deals.
- Acquired approximately **4-8 new customers per quarter** on average.
- Managed a team of **2-3 Sales representatives**.
- Delivered approximately **30% improvement in team performance and Sales revenue over
  the management period**.
- Expanded the customer portfolio by approximately **30% over the management period**.

Restrictions:

- Do not describe the 30% figure as annual or year-over-year growth.
- No monthly, quarterly, or annual quota amount is currently verified.
- No exact monetary Sales revenue or deal-value amount is currently verified.

### 7.5 Team Leader / Sales Supervisor scope

The role was approximately:

- 50% people/team management
- 50% direct Sales and account management

This is a verified `player-coach` profile. Responsibilities included:

- Managing 2-3 Sales representatives.
- New-employee onboarding and training.
- Setting individual and team goals.
- Allocating leads, accounts, or territories.
- Running recurring team meetings.
- Monitoring KPIs and individual performance.
- Pipeline management and Sales forecasting.
- Coaching and accompanying representatives in calls and meetings.
- Assisting with negotiation and closing.
- Approving discounts, pricing, credit, and commercial terms.
- Handling exceptional deals and strategic customers.
- Conducting performance reviews and giving feedback.
- Working with management on goals, forecasts, and team results.
- Participating in hiring and interviews only occasionally; this was not a central duty.

### 7.6 Tools and systems

- `Priority ERP`: orders, inventory checks, invoices, collection, and delivery-status
  tracking.
- `Excel`: Sales reports, KPI tracking, forecasts, performance tracking, and data
  analysis.
- Internal inventory/order system: availability, order processing, and operational
  follow-through.
- `Outlook` and `Gmail`: business communication with customers and internal parties.
- `WhatsApp`: ongoing customer communication, follow-up, and deal progression.
- `Teams`: internal communication and collaboration.

These tools support Sales operations, pipeline management, forecasting, and commercial
execution. They must not be used to claim a separate Sales Operations job that was not
held.

### 7.7 Activity mix

Lead-source mix, approximately:

- Proactive outbound: 25%
- Inbound leads: 20%
- Referrals and business relationships: 50%
- Tenders: 5%

Work-mode mix, approximately:

- Phone, email, WhatsApp, and digital work: 60%
- In-person meetings and field Sales: 40%

Interpretation constraint: this was not a classic SDR role based mainly on cold
outreach. Outbound experience may be emphasized when relevant, but the broader and
relationship-led nature of the role must not be hidden.

### 7.8 Sales velocity and repeat business

- A typical new deal often closed on the same day or within several days.
- Larger deals, chains, and tenders had a variable cycle from one day to approximately
  one month depending on complexity, customer, and existing relationship.
- Recurring-customer order frequency varied: daily, weekly, biweekly, or monthly.
- Some strategic customers placed frequent and more regular or substantial repeat
  orders.

This supports both high-velocity Sales and more complex B2B transactions. Do not claim
one fixed long Sales cycle.

### 7.9 Verified qualitative achievements

The following may be used without invented amounts, percentages, customer names, or
rankings:

- Expanded activity within existing accounts.
- Reactivated inactive customers.
- Acquired significant customers who became repeat customers.
- Closed business in difficult market conditions.
- Increased Pcom Solutions' share of existing customers' purchasing activity.
- Resolved commercial and operational crises that retained customers.
- Won complex deals and tenders.
- Coached Sales representatives and improved their performance.
- Improved pipeline management and follow-up processes.
- Expanded the customer portfolio, with only the separately verified approximately 30%
  figure allowed.

### 7.10 Canonical language proficiency

The following language levels are canonical and must be migrated to `base/common.md`:

- Hebrew: Native
- English: Fluent
- Arabic: Conversational
- French: Conversational

Language levels must not be strengthened or weakened during translation or tailoring.
The selected rendering schema may omit a language only when its section is optional and
the omission is justified by space or job relevance; omission does not change the
canonical proficiency level.

### 7.11 Logistics and professional contact facts

Canonical independent facts:

- Driving license: yes.
- Private vehicle: yes.
- Willing to travel nationwide: yes.
- Verified nationwide field-Sales experience: yes.

Do not infer one of these facts from another.

Contact policy:

- Include professional contact information only.
- Do not include photo, birth year, age, or marital status.
- LinkedIn is included by default in all Profiles if current and consistent.
- GitHub is included by default for Development.
- GitHub is optional for Tech Sales, Pre-Sales, or Solutions Consultant when it adds
  relevant evidence.
- GitHub is normally omitted for classic Sales Profiles.
- Portfolio or other professional links follow the same relevance rule.

### 7.12 Verified Tech Sales boundary

Verified combination:

- B2B Sales of mobile devices and related commercial solutions.
- Hands-on professional software-development experience at PH.Digital.

Not verified:

- Direct Sales of software, SaaS, subscriptions, or software services.

Tech Sales may combine the two independent bodies of experience. It must not imply that
the candidate previously sold SaaS or software.

## 8. Career narrative and PH.Digital weighting

### 8.1 Career narrative

The transition should be framed as career expansion, not leaving and returning:

- The candidate built a substantial B2B Sales career at Pcom Solutions, first in field
  Sales and later as a Team Leader / Sales Supervisor while remaining commercially
  active.
- The later Full-Stack Developer role at PH.Digital added technical depth, analytical
  thinking, and stronger understanding of products, systems, and technology processes.
- The current move toward Sales is a deliberate return to core strengths in customer
  relationships, selling, negotiation, business development, and management.
- Development is an added advantage, especially in technology environments; it is not
  described as a failed career choice.

Avoid negative narratives such as "development is not for me" or "I am giving up on
development."

### 8.2 Dynamic PH.Digital relevance

PH.Digital is secondary and dynamically weighted in Sales CVs:

- Tech Sales, SaaS-targeting roles, Pre-Sales, and Solutions Consultant: include real but
  shortened Development experience. It is meaningful evidence of technical orientation
  and ability to communicate with developers and technical customers.
- Account Executive, Business Development, or Account Manager at a technology company:
  include the role briefly, normally with one or two business-value-oriented bullets.
- Classic field Sales, SDR/BDR, Key Account Manager, or non-technical Sales management:
  reduce it substantially and omit it if it displaces more relevant Sales experience.

The PH.Digital fact itself never changes; only Profile-specific selection and weight do.

## 9. Tracks, Profiles, and Emphasis

### 9.1 Supported v1 Tracks

- `development`
- `sales`
- `tech-sales` may be represented as a Track or a Sales Profile internally, provided
  observable behavior remains as specified.

### 9.2 Supported Sales Profiles

- Field Sales
- Account Manager
- Key Account Manager
- SDR/BDR
- Account Executive
- Business Development
- Sales Management / Team Leadership
- Tech Sales
- Pre-Sales / Solutions Consultant where fit is reasonable

Explicitly excluded as target Profiles for now:

- Partnerships / Channel Sales
- Customer Success with commercial responsibility
- Sales Operations as a standalone claimed role

### 9.3 Profile versus Emphasis

Profile and Emphasis are separate decisions. Example: an Account Executive Profile may
have either New Business or Tech/Consultative Sales emphasis.

Supported Sales emphasis categories:

- `new-business`
- `account-growth`
- `leadership`
- `tech-consultative-sales`
- `balanced-sales`

The system automatically chooses Track, Profile, and Emphasis from the job description,
then reports a short explanation and confidence.

### 9.4 Confidence and approvals

Required flow:

`auto-classify -> confidence check -> approval only when needed -> user override wins`

- Clear, high-confidence classification proceeds automatically unless manual mode is
  enabled.
- Ambiguous classifications stop when the decision materially changes the CV, such as
  Sales versus Tech Sales or Account Executive versus Business Development.
- User override always wins and must be recorded.

### 9.5 Headline policy

- The top professional headline may use the normalized target role when actual
  experience reasonably supports that positioning.
- Historical job titles remain canonical and may not be rewritten into target-role
  titles.
- When fit is indirect, use a safe combined headline such as
  `B2B Sales | Account Management | Business Development`.
- Development title safeguards against invented seniority remain required.

## 10. Fit and gap analysis

The gap engine is decision support, not only a writing tool.

### 10.1 Fit levels

- **High fit**: proceed automatically.
- **Medium fit**: show important gaps and the planned factual writing strategy, then
  continue by default while allowing the user to stop.
- **Low fit / missing threshold requirement**: stop before CV generation and request a
  user decision.

User override always wins, but never authorizes fabricated experience.

### 10.2 Gap behavior

Distinguish livable gaps from material requirements such as:

- Mandatory years of experience in an absent field.
- A required market background that is genuinely missing.
- A required certification or tool used as a hard threshold.
- Direct SaaS Sales when only device Sales plus separate Development experience are
  verified.

If Salesforce is required but not verified, the system may highlight Priority ERP,
pipeline, and relevant business-tool experience. It must not claim Salesforce.

Gap results must distinguish hard gaps/failures from warnings.

## 11. Language behavior

### 11.1 Selection

- Hebrew job description -> Hebrew CV by default.
- English job description -> English CV by default.
- Mixed job description or international company -> dominant job-description language.
- Explicit user selection overrides automatic detection.

Canonical facts are stored once and are not language-specific. Translation may change
wording, but not meaning, numbers, certainty, or factual scope.

### 11.2 Hebrew rendering

A Hebrew CV requires:

- Full RTL document layout.
- Hebrew narrative text and natural Hebrew descriptions.
- Industry-standard English terms retained where appropriate, including B2B, CRM,
  Priority ERP, Excel, KPIs, pipeline, upsell/cross-sell, SaaS, and Full-Stack.
- Canonical English job titles may remain in English.
- Explicit mixed-direction handling for percentages, dates, phone numbers, email
  addresses, company names, and technical terms.

Rule:

`Hebrew CV = full RTL layout + Hebrew narrative + preserved standard English terminology`

## 12. Sales rendering schema and design

Sales has its own rendering schema. It is not a copy of the fixed Development skeleton.

### 12.1 Length

- Default target: one page.
- Two pages are allowed only when role seniority or complexity justifies them under
  rendering rules.
- Page count is validated, not assumed.

### 12.2 Sections

Required concepts:

- Professional contact information
- Professional Summary
- Work Experience
- Core Skills

Conditional concepts:

- Leadership
- Tools
- Technology background
- Selected achievements
- Education and languages when relevant to the schema

Section order and inclusion depend on Profile and job relevance. Facts remain canonical
regardless of presentation.

### 12.3 Visual priority

Design target:

`Modern visual polish + conservative ATS-safe structure`

Use typography, spacing, hierarchy, and restrained emphasis. Avoid complex tables,
meaning-dependent icons, progress bars, dense columns, graphics, and layouts that make
text extraction unreliable.

## 13. Draft, approval, rendering, and artifact lifecycle

### 13.1 Default flow

`Job input -> analysis -> draft -> pre-render validation -> user review/approval -> HTML -> PDF -> post-render validation -> ready -> tracking`

Show the user the draft, key tailoring decisions, and warnings before final rendering.

### 13.2 Fast mode

An explicit fast mode may generate Markdown, HTML, and PDF without pausing for manual
review. It may not skip any content, claim, rendering, ATS, or safety validation.

### 13.3 Meaningful versions only

- Keep one active working draft that may be updated.
- Preserve every user-approved draft as a historical version.
- Preserve every rendered HTML/PDF version and reference it in SQLite.
- Mark the exact version submitted to an employer.
- Submitted versions are immutable and never overwritten.
- A material post-approval edit creates a new approved version.
- Rejected experiments and transient wording drafts may be overwritten or removed from
  the working area.

Store metadata including:

- `version_number`
- `created_at`
- `approved_at`
- lifecycle status
- Track/Profile/Emphasis
- fact-set version
- content hash

### 13.4 Recruiter-facing filename

Format:

`Matan Malka - <Normalized Target Role> - CV.pdf`

Examples:

- `Matan Malka - Account Executive - CV.pdf`
- `Matan Malka - Business Development - CV.pdf`
- `Matan Malka - Sales Team Leader - CV.pdf`
- `Matan Malka - Full Stack Developer - CV.pdf`

The name derives from normalized Profile/target role, not necessarily the job posting's
full marketing title. Remove unnecessary strings such as market, B2B, SaaS, location,
and unsupported seniority. Use `B2B Sales` when no narrow Profile is safe. Manual
override is allowed and recorded.

## 14. Ready validation contract

`ready` is a strong status and requires all of the following:

`content-valid + profile-valid + structurally-valid + render-valid + ATS-readable + visually-valid`

Required validation groups:

1. **Content validation**
   - No unsupported facts, invented metrics, date conflicts, or changed historical job
     titles.
2. **Profile/Fit validation**
   - Selected content is consistent with Track, Profile, Emphasis, and accepted gaps.
3. **Structure validation**
   - Required sections exist, ordering is allowed, and prohibited/missing content is
     detected.
4. **Page-count validation**
   - One page by default; two pages only when allowed by the selected schema.
5. **PDF generation validation**
   - PDF exists, is nonempty, readable, and not corrupt.
6. **PDF text-extraction validation**
   - Compare extracted PDF text with source content to detect missing, broken, or
     non-ATS-readable text.
7. **Link validation**
   - LinkedIn, GitHub/Portfolio where included, email, and other links resolve to the
     intended configured values.
8. **Visual validation**
   - Detect overflow, clipping, broken headings, off-page elements, and material spacing
     problems.
9. **Direction validation**
   - Validate RTL/LTR and mixed-direction behavior for B2B, percentages, phone numbers,
     dates, email addresses, and system names.
10. **Filename and metadata validation**
    - Filename and normalized role are correct and do not introduce unapproved seniority
      or specialization.

Hard failures block `ready`. Warnings are shown and recorded but may be accepted when
they do not compromise factual or artifact integrity.

## 15. Job input, snapshots, and analysis versioning

### 15.1 Default job input

Company, role, URL when available, and full job-description text remain the core input.

External research is optional and occurs only on explicit request. When enabled, it may
help understand the company, product, and market. It may not add candidate facts or
silently redefine job requirements.

### 15.2 Immutable job snapshots

For every application, preserve:

- Original job text exactly as entered or retrieved.
- Source URL when present.
- Capture timestamp.
- Source metadata.

Never overwrite the original snapshot. A later update becomes a new snapshot linked to
the prior version.

Structured analysis is stored separately and may be rerun/versioned. It should include:

- Mandatory and preferred requirements
- Responsibilities
- Seniority
- Market/domain
- Tools
- Keywords
- Track/Profile/Emphasis and confidence
- Fit and gaps

Every approved CV version and decision record references its exact `job_snapshot_id`.

## 16. Decision records and reproducibility

Every approved CV version must have a permanent decision record containing at least:

- Company and target job.
- Track, Profile, Emphasis, confidence, and short rationale.
- Fit result and important gaps.
- Selected fact IDs.
- Relevant omitted facts and the main omission reason.
- Material derived statements.
- Accepted warnings or gaps.
- User overrides.
- Fact-store version.
- Links/references to CV Markdown, HTML, and PDF artifacts.
- Exact `job_snapshot_id` and job-analysis version.

Keep two representations:

- Structured data for validation and future analysis.
- A short human-readable summary.

Do not store or request hidden chain-of-thought. Store decisions and outcomes only.

### 16.1 Execution provenance

For meaningful runs and approved versions, store:

- `run_id`
- `created_at`
- `engine_version`
- `profile_version`
- `rendering_rules_version`
- `facts_version`
- `ai_provider`
- `ai_model`
- `task_contract_version`
- `prompt_version`
- `job_analysis_version`
- run-specific instruction overrides, if any

Prompts and task contracts should be version-controlled files; SQLite stores their
identifiers/versions. Preserve original outputs because matching metadata does not
guarantee deterministic AI text reproduction.

## 17. Application tracking and SQLite

### 17.1 Storage boundary

- Facts, Profiles, rendering rules, prompts, and contracts remain readable,
  version-controlled files.
- Applications, mutable statuses, history, actions, artifact references, and generation
  runs move to SQLite.
- Markdown/HTML/PDF artifacts remain files on disk; SQLite references them.
- Provide CSV export for human inspection and backup.

Use Python `sqlite3` with a small repository layer in v1. SQLAlchemy is not required.

### 17.2 Application stages

Preparation/application pipeline:

- `saved`
- `preparing`
- `ready`
- `applied`
- `recruiter_screen`
- `interview`
- `assignment`
- `final_stage`
- `offer`
- `accepted`
- `rejected`
- `withdrawn`
- `closed`

Store fields such as:

- `last_contact_date`
- `next_action`
- `next_action_date`
- `notes`
- `source`

Do not add statuses merely for "waiting" or "follow-up"; use actions and dates.
Maintain immutable status history, not only current status.

### 17.3 Minimum conceptual entities

The final schema may differ internally, but v1 needs concepts equivalent to:

- `applications`
- `job_snapshots`
- `job_analyses`
- `status_history`
- `application_events`
- `artifacts`
- `artifact_versions`
- `decision_records`
- `generation_runs`

References must be relationally consistent and validated by the status/reconciliation
tool.

## 18. AI boundary and task contracts

The core must be provider-agnostic even if v1 implements only one provider adapter.

### 18.1 Core responsibilities

Deterministic or policy-controlled core logic includes:

- Workflow state
- Fact lifecycle
- Track/Profile/Emphasis schema and allowed values
- Confidence thresholds and approval routing
- Fit levels and hard-gap policy
- Claim/fact linkage enforcement
- Validation
- Rendering workflow
- Persistence and migration
- Artifact lifecycle

### 18.2 AI task examples

Provide task contracts for operations such as:

- `classify_job`
- `analyze_gaps`
- `select_relevant_facts`
- `draft_resume`
- `extract_claims`
- `explain_decisions`

Favor structured outputs containing Profile, Emphasis, confidence, gaps, fact IDs,
derived statements, and warnings. Code must not parse arbitrary prose to infer critical
state when a schema can be used.

### 18.3 Provider adapters

- Config or CLI chooses provider and model.
- Provider adapters translate shared task inputs to provider-specific calls and return
  shared schema outputs.
- Implement one real adapter in v1.
- Do not build unnecessary abstraction for many hypothetical providers.
- Provider failure and invalid structured output must be handled explicitly.

## 19. CLI requirements

The final command names are a technical choice, but the CLI must support the complete
v1 workflow without a Web UI, including:

- Ingest/create an application and immutable job snapshot.
- Analyze Track, Profile, Emphasis, confidence, Fit, and gaps.
- Apply manual overrides.
- Create or update the working draft.
- Validate before review.
- Approve a draft.
- Render HTML and PDF.
- Run all `ready` checks.
- Run explicit fast mode without bypassing validation.
- Transition application status and record history.
- Set next actions.
- Inspect applications, versions, decision records, and validation results.
- Export application data to CSV.
- Reconcile SQLite, artifacts, versions, and migrated historical outputs.
- Run migration and verification safely.

Temporary wrappers or aliases should preserve common old commands during transition,
but permanent compatibility with the legacy architecture is not required after a
successful migration.

## 20. Rendering and dependency baseline

Allowed focused dependencies for v1:

- Python
- Pydantic for Facts, Profiles, job analysis, Fit results, applications, and AI output
  contracts
- Jinja2 for Development/Sales and LTR/RTL HTML templates
- Playwright for browser-based PDF generation and rendering/DOM validation
- Python standard-library `sqlite3` for persistence

SQLAlchemy should wait until the Web app or PostgreSQL migration creates a real need.

Dependency principle:

> Use dependencies where they enforce contracts, reduce rendering risk, or simplify
> portability, not for convenience alone.

## 21. Migration requirements

Migration is a one-time transition to the new authoritative structure.

### 21.1 Safety sequence

1. Inspect and inventory current source files, CSV rows, output artifacts, and known
   anomalies.
2. Create and verify a complete timestamped snapshot/backup before mutation.
3. Test migration against a copy/snapshot, not the only live data.
4. Convert `base/cv_base.md` into modular fact sources without deleting the original
   before backup and verification.
5. Apply the canonical Pcom corrections in Section 7 to the new fact source.
6. Convert `jobs/status.csv` to SQLite while preserving meaning and artifact references.
7. Preserve all existing Development and CodeValue outputs exactly as historical
   artifacts.
8. Normalize or map paths without losing provenance.
9. Validate database relationships, artifact existence, application uniqueness, and
   historical semantics.
10. Only mark the migration successful after migration tests and reconciliation pass.

### 21.2 Required checkpoint

Before any irreversible migration step, confirm programmatically that:

- The snapshot exists and is complete.
- Restore instructions are available.
- Migration tests pass.
- No historical artifact or application row is unaccounted for.

If any check fails, stop. No additional user approval is needed when all checks pass and
the migration exactly follows this spec.

### 21.3 Legacy status mapping

At minimum:

- Legacy `draft` maps to `preparing` or `ready` based on validated artifact state, not by
  blind string replacement.
- Legacy `sent` maps to `applied` and retains its sent/application date.
- Empty `date_sent` remains empty unless a historical submission is actually verified.

The migration plan must define deterministic handling for every existing row and report
exceptions rather than guessing.

## 22. Testing requirements

Required test layers:

1. **Unit tests**
   - Validation
   - Status transitions
   - Filename normalization
   - Fact lifecycle
   - Profile/Emphasis rules
   - SQLite repositories
2. **Integration tests**
   - Job description through analysis, draft, validation, HTML, PDF, and tracking
3. **Golden fixtures**
   - Development
   - English Sales
   - Hebrew Sales
   - Tech Sales
4. **Rendering tests**
   - Page count, overflow, RTL/LTR, mixed direction, dates, percentages, B2B, and links
5. **PDF ATS tests**
   - Text extraction and source-text comparison
6. **Migration tests**
   - Run on a snapshot representing the legacy project and verify data/artifact
     preservation
7. **Regression tests**
   - Add a targeted regression for every material bug found later

Avoid broad pixel-perfect PDF comparisons because browser/font changes create false
positives. Use structural/visual checks and a small number of focused golden screenshots
where they add real value.

## 23. Optional future application artifacts

The architecture should allow, but v1 does not need to fully implement:

- Cover letter
- LinkedIn message to recruiter or Hiring Manager
- Application email
- Short application-form answers
- Later interview preparation answers such as "Why this role?", "Why this company?",
  and "Tell us about yourself"

All artifacts must eventually use the same job analysis and canonical fact set. A less
formal format does not relax factual rules.

## 24. Explicitly out of v1

- Web application and UI
- Full simultaneous support for multiple AI providers
- Automatic company research by default
- Success-rate dashboard and advanced analytics
- PostgreSQL and SQLAlchemy migration
- Full implementation of cover letters and outreach artifacts
- UI for editing Facts and Profiles
- Advanced CV-variant performance analysis
- Follow-up and recruitment-process automation
- Partnerships / Channel Sales Profile
- Customer Success Profile
- Sales Operations as a claimed target role

## 25. Implementation-agent mandate

The implementing agent must perform:

`Review -> Architecture -> Plan -> Implement -> Test -> Migrate -> Verify`

### 25.1 Default autonomy

- Review the current repository and this spec.
- Identify conflicts, risks, and hidden migration issues.
- Produce a final architecture consistent with this spec.
- Continue automatically to a detailed implementation plan and implementation when no
  blocker or semantic deviation exists.
- Implement incrementally and test after each stage.
- Create and verify the migration snapshot before touching historical state.
- Finish with a working v1 and evidence that the Definition of Done passes.

### 25.2 Mandatory stop conditions

Stop and request a decision only for:

- A real contradiction in this specification.
- A required semantic product change.
- An unresolved behavior not answered by this specification that materially affects the
  user or data.
- A material risk of losing or corrupting historical information.
- A migration-safety failure.

Do not stop for ordinary internal implementation decisions.

### 25.3 Prohibited behavior

- Do not silently change product decisions.
- Do not fabricate candidate facts.
- Do not treat the AI model as a source of truth.
- Do not overwrite submitted or historical artifacts.
- Do not migrate without a verified snapshot and tests.
- Do not preserve legacy architecture when it undermines the specified v1 design.
- Do not implement deferred features merely because the architecture anticipates them.

## 26. Final v1 acceptance checklist

The upgrade is complete only when all items below are demonstrably true:

- [ ] Modular Common, Sales, Development, and Situational fact sources exist.
- [ ] Every migrated fact has one canonical location and stable identity.
- [ ] Canonical Pcom facts match Section 7, not stale legacy claims.
- [ ] Development behavior remains supported after migration.
- [ ] Sales and Tech Sales Profiles work with dynamic Emphasis.
- [ ] Track/Profile/Emphasis classification returns confidence and supports override.
- [ ] High/medium/low Fit and hard-gap behavior work as specified.
- [ ] Pending/confirmed/canonical lifecycle is implemented.
- [ ] Unsupported factual claims block approval and fast-mode output.
- [ ] English and Hebrew CV generation work.
- [ ] Hebrew RTL and mixed-direction checks pass.
- [ ] Sales has a distinct dynamic rendering schema.
- [ ] Default review-before-rendering and explicit fast mode both work.
- [ ] HTML and PDF are generated from the approved source through the engine.
- [ ] `ready` requires all content, structure, rendering, ATS, link, direction, filename,
      and visual checks.
- [ ] Recruiter-facing filenames use the normalized target role.
- [ ] SQLite stores applications, immutable job snapshots, status history, actions,
      artifact versions, decision records, and generation metadata.
- [ ] CSV export works.
- [ ] Approved and submitted artifact version behavior is correct and submitted files
      are immutable.
- [ ] One provider-agnostic AI task interface and at least one working adapter exist.
- [ ] Prompts/contracts and execution versions are traceable.
- [ ] Unit, integration, golden, rendering/ATS, migration, and regression tests pass.
- [ ] A verified snapshot exists for the legacy state.
- [ ] Historical applications and Development/CodeValue artifacts are preserved.
- [ ] Migration reconciliation reports no missing or unaccounted-for data.
- [ ] The CLI completes the v1 Definition of Done without a Web UI.
