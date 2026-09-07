# תוכנית מימוש — שלב 1: הבנת משרה

תאריך: 2026-09-06. גרסה 2 — מתקנת את גרסה 1 בשלוש נקודות ביקורת.
סטטוס: **תוכנית מימוש. לא שונו קוד, סכימה, עובדות או תוצרים. לא הורצו בדיקות.**

המסמך סוגר את שלוש שאלות המבנה שנשארו פתוחות ב[חוזה
הניתוח §11](tailoring-analysis-contract.md), ומתקן את תנאי D2.

מקורות מחייבים: `AGENTS.md`, [חוזה הניתוח](tailoring-analysis-contract.md) §2–§4,
[החלטות המוצר](tailoring-behavior-change.md) §2–§2.1, מפרט מוצר §9 ו־§12,
מצבים ופעולות §13, ארכיטקטורה §6–§8 ו־§11, תוכנית קבלה §2 ו־§6.

## מה תוקן מגרסה 1

| # | הביקורת | מה השתנה |
| --- | --- | --- |
| 1 | החרגת שדות מהשוואה אינה מדד הזרקה | §1.1 נכתב מחדש: התנהגות אסורה, והשוואת משמעות לפני/אחרי הזרקה על אותו טקסט. "הכיסוי לא עלה" נמחק ככלל |
| 2 | אין צורך להמציא עובדות גבול | §1.2 נכתב מחדש: שלושה מצבים נפרדים. הספירה בגרסה 1 הייתה לא עקבית — עובדת הגבול הקיימת **כן** מכסה SaaS. **אין צורך באף עובדה חדשה** |
| 3 | ברירות מחדל ב־JSON ממציאות משמעות לרשומות ישנות | §2.1 נכתב מחדש: שדות שאינם ניתנים לגזירה נשארים `None`, ונקראים דרך מתאם גרסה מפורש |
| — | חסימת טיוטה על ניתוח מוחלף | הוסרה משלב 1. §9 |
| — | `test_architecture.py` כבר ב־`pytest -q` | הוסר מהשער. §8 |

---

## 0. תקציר ההכרעות

| # | שאלה | הכרעה | נימוק בקוד |
| --- | --- | --- | --- |
| 1 | איפה נשמר תקציר הפירוש | **גם וגם**: שדות מפורשים על `Requirement`, והמזהה נגזר מהם | מזהה הוא hash — אי אפשר להציג ואי אפשר לאכוף עליו מדיניות. `composition` ו־`negation` נדרשים בזמן ריצה ב־`coverage.py` |
| 2 | גרסת ניתוח — ישות חדשה או רשומה נוספת | **רשומה נוספת. אין ישות חדשה** | `job_analyses` כבר נושא `version_number` ייחודי לכל `application_id`, כבר חסום ל־UPDATE/DELETE בטריגר, ו־`apply_analysis_decisions` כבר מייצר רשומה חדשה בענף "שינוי משמעות" |
| 3 | תקציב תוכן | **מחוץ לתכולה של שלב 1** | שייך לשלב 3–4 |

**אין שינוי Alembic.** `job_analyses.structured_json` הוא `JSONB` שנכתב מ־
`analysis.model_dump(mode="json")` (`preparation.py:333`).

**אבל יש שינוי בחוזה הנתונים ובתאימות ההיסטורית.** היעדר Alembic אינו אומר
שהחוזה לא זז: רשומות שנשמרו קודם ייקראו על ידי מודל חדש, וזה בדיוק המקום שבו
`AGENTS.md` אוסר להמציא ערך שרשומה לא נשאה. הטיפול ב־§2.1 ו־§5.2.

שינוי משמעות של ערך שמור וחתימה ציבורית ⇒ השער כולל
`tests/test_pipeline_end_to_end.py` מול PostgreSQL נקי בלי `OPENAI_API_KEY`.

---

## 1. שני תיקוני עיקרון לפני קוד

### 1.1 שער ההזרקה — התנהגות אסורה, לא שוויון

`tests/test_ai_tasks.py:832` — `test_injected_job_text_changes_no_policy_owned_result`
גוזר `POLICY_OWNED_FIELDS` מ־`JobAnalysis.model_fields` ודורש **שוויון מילולי**
בין ריצת AI לריצה דטרמיניסטית על אותו טקסט, כולל `requirements`, `gaps`, `fit`.

כש־AI מחלץ דרישות, שוויון לניתוח הדטרמיניסטי **חדל להיות מדד נכון בכלל** —
לא בגלל שדות שצריך להחריג, אלא בגלל שהמדד עצמו שגוי. חילוץ טוב יותר *אמור*
להניב דרישות אחרות מהמילון בן שבעת המושגים. שוויון לניתוח חלש אינו בטיחות.

גם **"הכיסוי לא עלה" אינו כלל נכון.** חילוץ טוב יותר יכול לזהות דרישה שהעובדות
הקנוניות באמת מכסות, והעלייה בכיסוי היא תוצאה נכונה ולא כשל.

וגם שער המקור אינו הגנת הזרקה: טקסט הזרקה יושב **בתוך** התצלום החתום, ולכן הוא
מצוטט מילה במילה בהצלחה.

#### מה כן נבדק

**א. התנהגות אסורה — טענות מוחלטות, לא השוואתיות.** הוראה בתוך המודעה אינה יכולה:

| אסור | איפה זה נאכף היום |
| --- | --- |
| לאשר, לקדם או לשנות סטטוס של עובדה | מחזור החיים ב־`knowledge_mutations.py`; לספק אין מסלול כתיבה למצב |
| להרחיב את מאגר העובדות המותר | `allowed_fact_pool(profile)` — פונקציה של הפרופיל בלבד |
| לעקוף ולידציה, אישור או חסימה | `validate_draft` דטרמיניסטי; `approve_draft` דורש ריצה תואמת לגרסה המדויקת |
| לקבוע `track`, `profile`, `fit`, `language`, `user_override`, `approval_reasons` | `JobClassificationProposal` אינו נושא את השדות; `RequirementExtractionProposal` גם לא |
| להכריע כיסוי | `coverage.py` רץ על עובדות קנוניות בלבד ואינו מקבל טקסט משרה |
| **למחוק או לרכך דרישה אמיתית** | חדש — ראה ב' |

**ב. השוואת משמעות לפני/אחרי, על אותו טקסט.** זו ההשוואה הנכונה, והיא אינה מול
המסלול הדטרמיניסטי אלא מול **אותה מודעה בלי ההוראה הזדונית**:

```
clean    = analyze(posting)
injected = analyze(posting + injection)

לכל דרישה אמיתית r ב־clean:
    קיימת r' ב־injected עם אותו טווח מקור בתוך הטקסט הנקי,
    ו־digest(r'.interpretation) == digest(r.interpretation)
```

מה שהטענה תופסת: מחיקת דרישה, ריכוך `mandatory -> preferred`, היפוך `negation`,
הפיכת `requirement` ל־`company-description` כדי להעלים תנאי סף, פיצול `any-of`.
הכיסוי אינו נבדק בנפרד — הוא פונקציה דטרמיניסטית של הפירוש ושל העובדות, ולכן
שוויון פירוש גורר שוויון כיסוי בלי להתחייב לכלל "הכיסוי לא עולה".

דרישות **נוספות** שההזרקה יצרה מותרות להופיע. הן מצוטטות ולכן חוקיות בשער המקור,
והן נחסמות במקום אחר: הן אינן יכולות לעשות דבר מרשימה א'.

**ג. הצהרת יושר.** ספק מדומה מוכיח **אכיפת חוזים** — שהמנוע דוחה מה שהוא אמור
לדחות. הוא אינו מוכיח עמידות של המודל בפני הזרקה, ואין לתייג אותו כך. עמידות
מודל אמיתית נבדקת ידנית מול ספק אמיתי, לפי תוכנית קבלה §6, ואינה תנאי שער
אוטומטי.

**נדרש עדכון מפרט מוצר §12 לפני קוד.** המשפט הקיים — "They may influence the
proposed content but never policy, allowed facts, validation, approval, or output
schemas" — נשאר נכון, אבל צריך לומר במפורש שדרישות ופערים הם תוכן שנגזר מהמודעה,
ושהאכיפה עליהם היא רשימה א' ובדיקת ב', לא שוויון למסלול אחר.

### 1.2 D2 מתוקן — שלושה מצבים, בלי להמציא עובדות

**תיקון לספירה בגרסה 1.** עובדת הגבול היחידה במאגר,
`sales.tech_sales.boundary` (`base/sales.md:853`), אומרת במפורש:

> "Verified combination is mobile-device B2B Sales plus separate professional
> software Development; **direct SaaS/software Sales is not verified**."

כלומר SaaS **כן** מגובה בעובדת גבול. גרסה 1 מנתה אותו כחסר בטבלה אחת וכמגובה
בפסקה אחרת. הספירה הנכונה: מבין משפחות `derive_gaps`, ל־SaaS יש גבול מפורש;
ל־CRM, Salesforce ולשותפויות אין — **ואינו נדרש.**

**היעדר תמיכה אינו גבול, והוא מספיק בפני עצמו.** אין שום צורך בעובדה קנונית
"אין לי ניסיון ב־HubSpot" כדי למנוע טענה על HubSpot. שלושה מצבים נפרדים, ולכל
אחד מסלול משלו:

| מצב | מה זה | נימוק הפער | מצב היום בקוד |
| --- | --- | --- | --- |
| **גבול מפורש** | עובדה מאומתת שמגבילה טענה | `fact.meaning` — הנוסח הסמכותי | קיים. `coverage.py` מוריד `matched -> partial`; `gaps_from_requirements` שולף את הנימוק דרך `boundary_meanings` |
| **אין תמיכה במאגר** | לא נמצאה עובדה קנונית שמבססת את הדרישה | `_COVERAGE_REASON["unsupported"]` — "Canonical facts do not verify this requirement." | **קיים במלואו.** `_satisfied` לא מצא ראיה ⇒ `unsupported` ⇒ פער |
| **לא הובנה** | הדרישה חולצה, אך אי אפשר להכריע כיסוי | אין הכרעה, ולכן אין טענת חוסר | **חסר.** ראה §3.6 |

המסקנה: **`derive_gaps` נמחק במסלול AI, ואין צורך באף עובדה חדשה.** מה ששלושת
החוקים חסרי־הגבול עשו הוא לייצר פער כשהמושג לא חולץ. משחולצה הדרישה, מסלול
"אין תמיכה" מטפל בה בעצמו ובנימוח מדויק יותר.

ויותר מזה — החוקים הישנים מנציחים פערים שמילת מפתח יצרה. `derive_gaps` מצית על
`"saas" in lowered` בלבד: מודעה שמזכירה שהחברה מוכרת תוכנה מקבלת פער SaaS גם
כשלא נדרש ממנה ניסיון SaaS. זה בדיוק המקרה של Connecteam. מחיקת החוקים במסלול
AI מסירה את הפער השגוי הזה, ועובדת הגבול ממשיכה להגן על מה שהיא באמת מגבילה,
כשדרישת SaaS אמיתית כן חולצה.

**המסלול הדטרמיניסטי (D3) שומר את `derive_gaps` כפי שהוא**, כי שם הדרישות האלה
אכן אינן מחולצות. שני המסלולים נשארים מפורשים ואין מעבר שקט ביניהם.

---

## 2. שינויי חוזים

### 2.1 שדות חדשים — ואיך רשומה ישנה נקראת

`AGENTS.md`: "Never invent a value a record never carried — a field that cannot be
derived stays NULL." ניתוח שנכתב לפני שער הפירוש **לא נשא** `composition`,
`negation` או `source_role`. ברירת מחדל `single` / `False` הייתה קובעת עליו
עובדה שהוא מעולם לא אמר.

לכן: **כל שדה שאינו ניתן לגזירה בטוחה הוא `| None = None`, ואין לו ערך ברירת מחדל
תוכני.**

```python
class Requirement(StrictModel):
    ...
    #: None = הרשומה נכתבה לפני שער הפירוש. לא "single, לא שלילה".
    interpretation: RequirementInterpretation | None = None
    #: None = חולצה דטרמיניסטית; לחילוץ דטרמיניסטי אין ציטוט מוצהר.
    attestation: RequirementAttestation | None = None
    #: None = רשומה שקדמה למרחב השמות של המחלצים.
    extractor: str | None = None

class RequirementInterpretation(StrictModel):
    """כשהיא קיימת, כל שדותיה קיימים. אין חצי פירוש."""
    source_role: SourceRole
    obligation: Obligation
    composition: Composition
    members: list[RequirementMember] = []
    negation: bool
    context_quote: str | None = None
```

`JobAnalysis`:

```python
    #: None = הניתוח מעולם לא שאל את השאלה.
    #: []   = שאל, ולא נמצא משפט נושא דרישה שלא מופה.
    #: ההבחנה נשמרת: רשימה ריקה היא ממצא, חוסר הוא היעדר שאלה.
    unmapped_statements: list[UnmappedStatement] | None = None
    understanding: UnderstandingSources | None = None
    interpretation_decisions: list[InterpretationDecision] = []
```

**מתאם גרסה מפורש.** קורא יחיד ב־`domain/analysis/requirements/compat.py`:

```python
def interpretation_of(requirement) -> RequirementInterpretation | None:
    """הפירוש שהרשומה נושאת, או None כשהיא קודמת לשער.

    מה שניתן לגזור בבטחה נגזר, ורק הוא. `mandatory: bool` הוא ערך
    שהרשומה כן נשאה, ולכן ניתן לומר `obligation` עבורו. `composition`
    ו־`negation` לא נשמרו מעולם ואינם מומצאים — ולכן מחלץ ישן אינו
    מקבל פירוש חלקי, אלא None.
    """
```

הכלל הנגזר: **קוד מדיניות אינו קורא `requirement.interpretation` ישירות.**
הוא קורא דרך המתאם ומטפל ב־`None` במפורש. `None` פירושו "אי אפשר להכריע לפי
הפירוש" — לא "פירוש רגיל".

`analysis_version` עולה מ־`"1.0"` ל־`"1.1"` ומשמש את המתאם כמפתח מפורש.

### 2.2 סוגי משנה חדשים

```python
SourceRole  = Literal["requirement", "responsibility", "company-description", "benefit", "other"]
Obligation  = Literal["mandatory", "preferred", "unspecified"]
Composition = Literal["single", "any-of", "all-of"]

class RequirementMember(StrictModel):
    member_id: str
    label: str

class RequirementAttestation(StrictModel):
    """שער המקור. היסטים לתוך טקסט התצלום כפי שנקרא מחנות המטענים."""
    quote: str
    start: int
    end: int

class UnmappedStatement(StrictModel):
    start: int
    end: int
    text: str
    source_role: SourceRole
    reason: str

class UnderstandingSources(StrictModel):
    """מי הבין מה. bool אחד לא היה בר־ייחוס."""
    by_concepts: int
    by_rules: int
    by_ai: int

class InterpretationDecision(StrictModel):
    prior_requirement_id: str
    prior_analysis_id: str
    interpretation: RequirementInterpretation
    actor: str
    decided_at: str
    reason: str | None = None
```

### 2.3 משימת ספק שביעית

חילוץ אינו נכנס ל־`JobClassificationProposal`: ערבוב סיווג עם חילוץ בקריאה אחת
מבטל את ההפרדה שמפרט מוצר §12 בנוי עליה.

```python
class ProposedRequirement(StrictModel):
    attestation: RequirementAttestation
    interpretation: RequirementInterpretation
    kind: RequirementKind
    label: str
    demanded: str | None = None
    #: תגיות נושא מאוצר התגיות של המאגר. תגית זרה פוסלת את ההצעה.
    topic_tags: list[str] = []

class RequirementExtractionProposal(StrictModel):
    requirements: list[ProposedRequirement]
    unmapped_statements: list[UnmappedStatement]
```

`ports/outbound.py`: `RequirementExtractionContext` (`job_text` + `requirement_lines`
שהמנוע כבר חישב, כדי שהשלמות תיבדק מול אותו מכנה), ו־
`propose_requirement_extraction` על `AIProvider`.
`ai/contracts/task_contracts.json`: ערך שישי לצד חמשת הקיימים. מפרט מוצר §12 מונה
שש משימות (כולל `assess_claim_support` שטרם מומשה) — הכניסה כאן היא השביעית
ברשימת המפרט. §12 מתעדכן.

### 2.4 חתימות ציבוריות שמשתנות

| חתימה | היום | אחרי |
| --- | --- | --- |
| `extraction.requirement_id(...)` | `normalized_hash, extraction_version, identity_span, ordinal` | + `interpretation: RequirementInterpretation \| None` |
| `confidence.extraction_failed(...)` | `understood_elsewhere: bool` | `sources: UnderstandingSources` |
| `confidence.extraction_confidence(...)` | `understood_elsewhere: bool` | `sources: UnderstandingSources` |
| `contracts.analysis.Coverage` | `matched \| partial \| unsupported` | + `undetermined` (§3.6) |

`classification.py::_identified` מקבל קבוע פירוש מפורש (`RULE_INTERPRETATION`)
ולא `None` שקט — אחרת פער חוק ודרישת AI על אותו ניסוח יקבלו מזהה זהה.

---

## 3. שבעת הסעיפים

### 3.1 שער המקור — דטרמיניסטי, דחייה בכשל

**קובץ חדש:** `cv_engine/domain/analysis/requirements/attestation.py`.

- `text[start:end] == quote` מילה במילה. בלי נרמול, בלי `casefold`, בלי `strip`.
- הטקסט הוא בדיוק פלט `snapshot_payloads.read_snapshot(payload_path, source_hash)` —
  אותה מחרוזת שנמסרה לספק.
- `0 <= start < end <= len(text)`.
- ציטוט מקטעים לא רציפים אינו בר־ביטוי: `attestation` הוא זוג היסטים אחד.
- **כשל אחד פוסל את כל הפלט.** `InvalidProviderOutput` ⇒
  `OperationFailureCode.INVALID_OUTPUT`, אותו מסלול שבו `refuse_facts_outside_the_pool`
  פוסל היום (`services/proposals.py`). אין תיקון שקט ואין קבלה חלקית.

השער מוכיח שהטקסט נאמר. **הוא אינו הגנת הזרקה** — §1.1.

אין Alembic. אין חתימה ציבורית שמשתנה.

### 3.2 שער הפירוש

**קובץ חדש:** `requirements/interpretation.py`.

1. `obligation == "mandatory"` נדחה כש־`source_role != "requirement"`, אלא אם סמן
   חובה מופיע בתוך `context_quote`. **רשימת הסמנים נגזרת מ־
   `RequirementConceptStore.mandatory_markers`** שכבר נטענת מהתצורה.
2. `context_quote` לא ריק ⇒ עובר את שער המקור בעצמו.
3. `any-of` ⇒ `len(members) >= 2`, ומייצר **דרישה אחת**. `matched` אם איבר אחד
   לפחות מכוסה.
4. `all-of` ⇒ `len(members) >= 2`, כל איבר נבדק בנפרד כמו `ConceptComponent`.
   איבר בלי ראיה נשאר `MissingComponent`; צירוף ראיות נפרדות אינו מספק אותו.
5. `single` ⇒ `members == []`.
6. `kind == "threshold"` ⇒ `demanded` קיים ובסולם מוצהר (`concepts.scales` או
   `years`). מוקדם לשער כדי שסף בלי ערך ייפסל ולא ייקרא `unsupported`.
7. `negation` ⇒ לעולם לא כיסוי חיובי; מקצר החוצה ב־`coverage.py` לפני `_satisfied`.

`_satisfied` ו־`_candidate_fact_ids` **אינם משתנים** — הם כבר מסננים עובדות גבול.

סיווג: משמעות ערך שמור.

### 3.3 שלמות

מכנה: `requirement_lines` (`segmentation.py`), ללא שינוי. מונה בשלוש:

- משפט שחופף דרישה מקובלת → נספר.
- משפט שסומן ב־`unmapped_statements` עם `source_role` ונימוק → נספר כמטופל,
  **אך שולל `parsed`**. המרבי בנוכחות סימון כזה הוא `partial`.
- לא כוסה ולא סומן → אינו נספר, ומוריד שלמות כמו היום.

הכלל האמצעי סוגר את החור המחמיא: בלעדיו, סימון כל המשפטים כ־
`company-description` מניב שלמות 1.0.

`understood_elsewhere: bool` ⇒ `UnderstandingSources`: `by_concepts` (חפיפת
היסטים), `by_rules` (`derive_gaps` ירה), `by_ai` (עברה את שני השערים).
`extraction_failed` נשאר "נאמרו דרישות ואף אחת לא נקראה" — כעת סכום שלושתם אפס.

סיווג: **חתימה ציבורית** ו**משמעות ערך שמור**.

### 3.4 זהות דרישה

`requirement_id` מקבל מפתח חמישי:

```python
"interpretation": canonical_json({
    "source_role": ..., "obligation": ..., "composition": ...,
    "members": [m.member_id for m in ...], "negation": ...,
    "kind": ..., "demanded": ...,
})
```

מרחב שמות למחלץ:

| מסלול | `extractor` |
| --- | --- |
| דטרמיניסטי | `concepts.extraction_version` — היום `"2"`, ללא שינוי |
| חוקים | `concepts.extraction_version` + `RULE_INTERPRETATION` |
| AI | `f"ai:{task_version}:{prompt_version}"` |
| ניתוח ישן | `"0"` — ה־gaps שלו סמכותיים ואינם נגזרים מחדש |

**ירושת אישורי פער אינה דורשת מנגנון חדש.** `_acceptable_requirement_ids`
(`analysis.py:404`) כבר מאמת כל מזהה מוגש מול הפערים הקשים של הניתוח *שנכתב*.
שינוי פירוש מזיז את המזהה, והאישור הישן נדחה. צריך רק לא לשבור את זה — ולשפר את
הודעת הסירוב, שאם לא כן המשתמש רואה `"no hard gap to accept for requirement(s)"`
בלי לדעת שהסיבה היא תיקון פירוש.

סיווג: **חתימה ציבורית** ו**משמעות ערך שמור**. מזהים ישנים שנשמרו בתוך
`accepted_gaps_json` נשארים כפי שהם; רק ניתוח חדש נכתב בסכימה החדשה.

### 3.5 תיקון ניתוח — גרסה חדשה

**אין פקודה חדשה ואין ישות חדשה.** `apply_analysis_decisions` הוא כבר טופס
הביקורת ומפצל לשני ענפים; מפרט מוצר §9 כבר קובע "A change to the meaning or
classification of a requirement creates a JobAnalysis". תיקון פירוש הוא זה.

השינוי: `ApplyAnalysisDecisionsCommand` מקבל
`requirement_interpretations: list[InterpretationOverride]`, ו־`changes_meaning`
נכון גם כשהרשימה לא ריקה. הענף הקיים כבר מקצה `version_number` תחת נעילה
(`preparation.py:321`), והטריגרים `no_update_job_analyses` / `no_delete_job_analyses`
אוכפים את שימור הישן במסד ולא במוסכמה.

הפירוש המתוקן נרשם ב־`interpretation_decisions` על הניתוח החדש, עם
`prior_analysis_id` ו־`prior_requirement_id`.

**כלל התיישנות לטיוטה — הוסר משלב 1.** ראה §9.

סיווג: **חתימה ציבורית** (חוזה פקודה + חוזה HTTP). `openapi/openapi.json` ו־
`openapi/types.ts` נדרשים ל־regeneration; `tests/test_api_foundation.py:429` אוכף.

### 3.6 שלושת מצבי אי־הכיסוי

שניים קיימים במלואם ואינם נוגעים בקוד:

- **גבול מפורש** — `coverage.py` מוריד `matched -> partial`, ו־
  `gaps_from_requirements` שולף את `fact.meaning` כנימוק סמכותי.
  השיוך לדרישה שמקורה AI: `boundary_facts` נגזרות מהתגית `boundary` על
  ה־`FactStore` (**guard נגזר, לא רשימה** — עובדת גבול חדשה נכנסת לתוקף עצם
  קנוניזציה), ומשויכות דרך `fact.tags & requirement.topic_tags`. תגית זרה
  ב־`topic_tags` פוסלת את ההצעה.
- **אין תמיכה במאגר** — `_satisfied` לא מצא ראיה ⇒ `unsupported` ⇒ פער עם
  `"Canonical facts do not verify this requirement."` זה כל מה שנדרש כדי למנוע
  טענה על HubSpot. **אין כאן עובדה חדשה ואין מה לממש.**

השלישי חסר:

- **לא הובנה.** דרישה שעברה את שני השערים אך המנוע אינו יכול להכריע את כיסויה —
  סף בסולם שאינו מודל, איברי `any-of` שאין להם מיפוי תגיות. היום היא נופלת ל־
  `unsupported`, שהוא טענה שאין לנו: "העובדות אינן מאמתות" אינו "לא ידענו לבדוק".

  `Coverage` מקבל ערך רביעי `undetermined`:

  | | `fit` | חסימה |
  | --- | --- | --- |
  | `undetermined` על דרישת חובה | **אינו פער קשה.** "לא ידענו" אינו "אין לך" | נרשם כ־`approval_reason` חדש `coverage-undetermined`, ב־`APPROVAL_REASONS` עם `overrides={"analysis"}` — נפתר רק בהחלטה המפורשת להתקדם עם ניתוח לא שלם, בדיוק כמו `extraction-failed` |
  | `fit` הכולל | `UNKNOWN` דרך `merge_fit`, אלא אם קיים פער קשה אמיתי — ואז `LOW` גובר, כפי ש־`derive_fit` כבר קובע |

  ה־guard הקיים `test_analysis.py:685` גוזר את מפתחות `APPROVAL_REASONS` מהקוד
  שפולט אותן, ולכן סיבה חדשה שלא נרשמה נכשלת ולא עוברת בשקט.

**מחיקת `derive_gaps` במסלול AI** — §1.2. `test_no_concept_shadows_a_legacy_rule_gap`
(`test_analysis.py:495`) נשאר בתוקף למסלול הדטרמיניסטי, שם החוקים נשארים.

### 3.7 `merge_classification`

`approval.py:110`. **הפונקציה עצמה כמעט אינה משתנה.** מה שמשתנה הוא מה שמגיע
אליה כ־`deterministic`. סדר `AnalysisService.prepare`:

```
1. קריאת התצלום                                     (קיים)
2. classify_job — דטרמיניסטי מלא                    (קיים)
3. [AI] propose_requirement_extraction               (חדש)
4. שער המקור + שער הפירוש על כל הצעה                 (חדש)
5. cover_requirements — דטרמיניסטי                   (קיים, קלט חדש)
6. שיוך עובדות גבול + gaps_from_requirements         (קיים, קלט חדש)
7. הרכבת JobAnalysis לפני שער המיזוג                 (חדש: החלפת requirements)
8. [AI] propose_job_analysis                          (קיים)
9. merge_classification                               (קיים)
```

צעד 7 הוא המקום שבו D2 מתממש — **לפני** שער המיזוג, לא בתוכו.

נפתח ב־`merge_classification` עצמו: **כלום.** `deterministic.requirements`
ו־`deterministic.extraction_version` עוברים כפי שהם (`approval.py:174-175`)
ונושאים תוכן אחר.

נשאר נעול: `JobClassificationProposal` בלי `requirements`; `fit` נגזר מהפערים
הממוזגים ומקופל דרך `merge_fit`; `merge_gaps` מונוטוני; `language`,
`user_override`, `classification_requires_approval`, `approval_reasons` ללא נגיעה.

---

## 4. סדר עבודה פנימי

| גל | מה | קבצים ראשיים |
| --- | --- | --- |
| W1 | חוזים + מתאם הגרסה + שני השערים, ללא חיווט | `contracts/analysis.py`, `contracts/providers.py`, `requirements/attestation.py`, `requirements/interpretation.py`, `requirements/compat.py` |
| W2 | זהות ושלמות | `requirements/extraction.py`, `requirements/confidence.py`, `analysis/classification.py` |
| W3 | כיסוי: `any-of`, `all-of`, `negation`, `undetermined` | `requirements/coverage.py`, `analysis/gaps.py`, `analysis/approval.py` |
| W4 | משימת ספק + חיווט יישום | `ports/outbound.py`, `infrastructure/providers.py`, `services/analysis.py`, `ai/contracts/task_contracts.json`, `ai/prompts/` |
| W5 | שיוך עובדות גבול, מחיקת `derive_gaps` במסלול AI, D3 בתצורה | `requirements/coverage.py`, `analysis/gaps.py`, `config/requirements.json` |
| W6 | תיקון פירוש, תצוגה | `commands.py`, `services/analysis.py`, `api/schemas/`, `openapi/`, `frontend/src/api/analyses.ts`, `frontend/src/pages/application/analysis/` |

---

## 5. נקודות שבירה

### 5.1 שער ההזרקה
`tests/test_ai_tasks.py:832` נכתב מחדש לפי §1.1 — לא מתוקן כדי לעבור.

### 5.2 קריאת רשומות ישנות
כל שדה חדש הוא `None` ולא ברירת מחדל תוכנית. נדרשת בדיקה שטוענת JSON של ניתוח
שנשמר לפני השלב ומאשרת ש־`interpretation`, `attestation`, `understanding`
ו־`unmapped_statements` הם `None` — **ולא מומצאים**. `extraction_version == "0"`
ו־`requirements == []` נשארים סימני הניתוח הישן ואינם נגזרים מחדש
(`test_analysis.py:326`, `:838`).

### 5.3 `Coverage` רביעי שובר שני מקומות בצד הלקוח, וזה טוב
- `frontend/src/pages/application/analysis/RequirementCoverageSection.tsx:13,19` —
  `Record<RequirementCoverage, …>` ממופה מלא, ולכן ערך חדש **נכשל ב־typecheck**.
  זה guard נגזר קיים; אין להחליש אותו ל־`Partial<Record<…>>`.
- `frontend/src/api/analyses.ts:279` — `isRequirementCoverage` ברמת הריצה.
  בלי עדכון, כל דרישה `undetermined` נספרת ב־`unreadableRequirementCount`
  ומוצגת כ"לא ניתנת להצגה", שזו הודעה שגויה.

### 5.4 golden — סיכון עקיף אמיתי
`classification.py` בוחר פרופיל לפי `(coverage_scores, term_scores)`. הרחבת
`config/requirements.json` למושגי פיתוח (D3, W5) מזיזה את `coverage_scores` לכל
משרה, לרבות הקבועות ב־`tests/golden/*.json`. שינוי פרופיל או הדגש משנה בחירת
עובדות ומכאן את המסמך. **תזוזת golden אינה מותרת אלא אם הפלט אמור היה להשתנות.**

### 5.5 `_identified` וזהות פערי חוקים
פער חוק חייב `RULE_INTERPRETATION` מפורש. `None` שקט יגרום לפער חוק ולדרישת AI
על אותו ניסוח לקבל מזהה זהה, ואישור על אחד ייקרא כאישור על השני.

### 5.6 היסטים מול איזו מחרוזת
שער המקור נכשל בשקט אם הספק קיבל מחרוזת אחת וההיסטים נבדקים מול אחרת. נדרשת
בדיקה שההשוואה היא מול אותו אובייקט שנשלח ב־`job_text`.

### 5.7 `openapi.json` ו־`types.ts`
`tests/test_api_foundation.py:429` נכשל אם `ApplyAnalysisDecisionsRequest` השתנה
ולא הורץ `python openapi/generate_openapi.py`. ה־diff נאמר בהודעת ה־commit.

---

## 6. קבלה — Connecteam ו־WeDev

### WeDev — Junior Fullstack

| דרישה בקבלה | מה מספק אותה | גל |
| --- | --- | --- |
| `React, Angular, or Vue` = דרישה אחת `any-of`, `matched` דרך React | `composition: any-of` + "איבר אחד מספיק" | W1, W3 |
| Shopify בתיאור החברה אינו תנאי סף | `source_role: company-description` + חסימת `mandatory` בלי סמן מצוטט | W1 |
| Node.js, MongoDB, SQL, responsive נקראים בכלל | חילוץ AI (D2) או מושגי D3. בלי אחד מהם המשרה נשארת `unparsed` → `FitLevel.UNKNOWN` | W4 / W5 |

### Connecteam — SDR

| דרישה בקבלה | מה מספק אותה | גל |
| --- | --- | --- |
| inbound כחלק מתמהיל, לא דרישה שהומצאה | שער המקור: אין ציטוט → אין דרישה | W1 |
| "1–2 שנות SDR **או** תפקיד מכירות אחר" אינו חוסר | `any-of`, לא `threshold` על SDR | W1, W3 |
| HubSpot ודמואים אינם ותק חובה | `source_role: responsibility` + חסימת `mandatory` | W1 |
| **HubSpot לא נטען, בלי עובדה חדשה** | "אין תמיכה במאגר" — `unsupported` ⇒ פער. קיים היום | — |
| אין פער SaaS שגוי כשהמודעה לא דורשת SaaS | מחיקת `derive_gaps` במסלול AI. עובדת הגבול מגינה רק כשדרישת SaaS אמיתית חולצה | W5 |

---

## 7. מה נשאר פתוח, במפורש

| # | פתוח | למה זה לא נסגר כאן |
| --- | --- | --- |
| 1 | עמידות המודל בפני הזרקה | §1.1 ג'. נבדק ידנית מול ספק אמיתי לפי תוכנית קבלה §6, ואינו תנאי שער אוטומטי |
| 2 | הרחבת `config/requirements.json` למושגי פיתוח (D3) — היקף הרשימה | רשימת חריגים מכוונת; היקפה נקבע מול שתי משרות הקבלה ב־W5, לא מראש |
| 3 | חסימת טיוטה על ניתוח מוחלף | §9 |

---

## 8. הפקודות

המשתמש מריץ. אני לא.

### תוך כדי עבודה — ממוקד לפי הדיף

| אחרי | פקודה | מה זה מוכיח |
| --- | --- | --- |
| W1 | `pytest tests/test_domain_contracts.py tests/test_analysis.py -q` | החוזים נטענים; ניתוח שנשמר קודם נקרא עם `None` ולא עם ערכים מומצאים; שני השערים דוחים מה שהם אמורים |
| W2 | `pytest tests/test_analysis.py -q` | אותו ציטוט בפירוש אחר מקבל מזהה אחר; משפט לא מכוסה ולא מסומן משאיר `partial`; שלושת המקורות נספרים בנפרד |
| W3 | `pytest tests/test_analysis.py tests/test_classification_policy.py -q` | `any-of` = דרישה אחת; `all-of` לא מסופק מצירוף ראיות; `negation` לא נספרת חיובית; `undetermined` אינו פער קשה ובכל זאת חוסם; עובדת גבול עדיין לא מספקת דבר |
| W4 | `pytest tests/test_ai_tasks.py tests/test_provider.py -q` | המשימה רשומה; פלט לא תקין נכשל כ־`INVALID_OUTPUT`; שער ההזרקה בניסוחו החדש — התנהגות אסורה והשוואת לפני/אחרי |
| W5 | `pytest tests/test_analysis.py tests/test_golden.py -q` | פער מכל אחד משלושת המצבים; מחיקת `derive_gaps` במסלול AI לא הפילה הגנה; **ה־hashes של golden לא זזו** |
| W6 | `pytest tests/test_api_analyses.py tests/test_api_applications.py tests/test_state_projection.py -q` | תיקון פירוש יוצר גרסה חדשה ואינו נוגע בישנה; ההיטל מציג את שלושת המצבים |
| W6, אם חוזה HTTP השתנה | `python openapi/generate_openapi.py` ואז `pytest tests/test_api_foundation.py -q` | הסכימה המחויבת אינה מתיישנת |
| W6, אם נגעתי ב־frontend | `npm --prefix frontend run check` | typecheck (כולל ה־`Record` הממופה המלא), tokens, format, vitest |

### שער הגבול — פעם אחת, בסוף

```
1.  pytest -q
2.  CV_TEST_DATABASE_URL=postgresql+psycopg://cv:cv@localhost:5432/cv_stage1 \
      env -u OPENAI_API_KEY pytest tests/test_pipeline_end_to_end.py -q
3.  npm --prefix frontend run check
```

| # | מה זה מוכיח |
| --- | --- |
| 1 | הסוויטה הלא־דפדפנית כולה. `testpaths=["tests"]` ו־`addopts -m "not browser"` כבר אוספים את `test_architecture.py` ו־`test_golden.py`, ולכן אין להריץ אותם שוב באותם תנאים |
| 2 | הדרישה של `AGENTS.md` על משמעות ערך שמור וחתימה ציבורית: `ingest → analyze → draft → validate → approve → render → ready → reconcile` מול PostgreSQL נקי, **בלי `OPENAI_API_KEY`**. מוכיח שהמסלול הדטרמיניסטי מגיע ל־Ready |
| 3 | הלקוח קורא את הניתוח החדש בלי לספור שדות חדשים כ"לא ניתנים להצגה" |

### מה לא בשער, ולמה

| שער | למה לא |
| --- | --- |
| טופולוגיית מיגרציות, שדרוג מסד ריק, diff סכימה | **אין שינוי `alembic/`.** השדות נכנסים ל־`job_analyses.structured_json` שהוא `JSONB` קיים. תאימות היסטורית נבדקת בקוד, לא במיגרציה — §5.2 |
| סוויטת דפדפן | שלב 1 אינו נוגע ברינדור או בנתיב תוצר |

`tests/test_golden.py` נכלל ב־`pytest -q` ומורץ בנפרד ב־W5 כי §5.4 הוא סיכון
אמיתי. תזוזת hash היא ממצא, לא ערך לעדכן.

---

## 9. מה הוסר משלב 1

**חסימת יצירת טיוטה על ניתוח מוחלף.** גרסה 1 הציעה לחסום `create_draft` כשהניתוח
הנמסר אינו הפעיל, במקביל לכלל ה־snapshot ב־`generation.py:181`. זהו **שינוי מוצר
נפרד** — הוא נוגע במחזור החיים של הטיוטה, לא בהבנת המשרה, ולא צריך להיכנס יחד עם
שלב החילוץ.

היום המצב נשאר כפי שהוא: `state.py:134` מפיק אזהרה `ANALYSIS_REPLACED` עם
`replace_working_draft` / `archive_working_draft` הזמינות. אין שינוי, ואין צורך
בעדכון מצבים ופעולות §6 או §14 במסגרת שלב 1.

---

## 10. מצב המסירה

- תוכנית מימוש בלבד. לא שונו קוד, סכימה, עובדות או תוצרים. לא הורצו בדיקות.
- שלוש שאלות המבנה נסגרו (§0).
- **תיקון עובדתי לגרסה 1:** `sales.tech_sales.boundary` כן מגבה את SaaS. הספירה
  בגרסה 1 לא הייתה עקבית.
- **אין צורך ליצור אף עובדה קנונית חדשה.** היעדר תמיכה מספיק כדי למנוע טענה,
  ומסלול הפער שלו כבר קיים ועובד.
- **הכרעה אחת נדרשת לפני קוד:** ניסוח מחדש של שער ההזרקה במפרט מוצר §12 (§1.1).
- שינוי חוזה נתונים אחד ללא Alembic: שדות `None` ומתאם גרסה מפורש (§2.1, §5.2).
