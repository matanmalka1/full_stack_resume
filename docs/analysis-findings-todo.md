# Analysis/Classification Findings — Verification & Fix-Order TODO

Source: external review (Claude web) of the requirement extraction / classification /
fit-scoring pipeline, triggered by a real production record (`SuperFunnel` /
Account Executive, application `90787e94-1401-44ba-b8e3-ef4e8aecccde`) where
`fit_score=1.0` was computed from a single extracted requirement while
`confidence=0.429`. Every finding below was re-verified directly against the code in
this session (file:line cited), independent of the external review's own citations.

**Planning only. No code changed. No tests run.**

## מצב נוכחי (למי שממשיך מכאן)

**Stage 1+2 נחת בקוד** (הסשן שאחרי התכנון). כל השאר — Stage 3-8 — עדיין תכנון
בלבד. 21 ממצאים מאומתים (D1-D9, A1-A11, C1-C2), סדר תיקון ב-8 שלבים.

### מה נחת בפועל ב-Stage 1+2

שבעת הצעדים של "Stage 1+2 — implementation file plan" יושמו כלשונם, בסדר הכתוב:

| # | קובץ | מה נחת |
| --- | --- | --- |
| 1 | `requirements/extraction.py` | קבוע `UNDETERMINED_INTERPRETATION`, `unmatched_requirement_lines()`, `undetermined_requirement()` (`mandatory=False`, `component_id="unmapped-statement"`). ה-discriminant מצורף **בתוך** ה-helper, לא אצל הקורא, כדי ששום קורא לא יוכל לשכוח אותו |
| 2 | `requirements/confidence.py` | `understood_elsewhere` הוסר מ-`extraction_failed` לגמרי (חתימה וגוף). נשאר קלט יחיד ל-`extraction_confidence` (רצפת 0.4), ללא שינוי |
| 3 | `gaps.py` | **לא נגעו.** כמתוכנן |
| 4 | `analysis/approval.py` | שתי רשומות חדשות ב-`APPROVAL_REASONS`, שתיהן `frozenset({"analysis"})`/`ANALYSIS_INCOMPLETE` |
| 5 | `analysis/classification.py` | `classify_job`: ספלייס, שני הבוליאנים inline, טרנרי ה-`fit_score`, שני ה-reasons, והערה מיושנת (שורות 466-470) תוקנה. `rebase_requirements`: שני פרמטרים מפורשים חדשים |
| 6 | `application/services/analysis.py` | `prepare()` מחשב טרי; `_correct_interpretations()` יורש מ-`approval_reasons` — אותה תבנית של `extraction_failed` |
| 7 | `requirements/ai_extraction.py` | ספלייס ב-`verify_and_cover_extraction`, ערך רביעי בהחזרה (`unmatched_lines`). `by_ai` ממשיך לספור `mapped_spans` בלבד. `extraction_is_failed` לא נגעו |

**סטטוס הממצאים אחרי היישום:**

- **D1 — סגור.** `fit_score=None` על `requirements_absent`, ב-`classify_job`
  ו-ב-`rebase_requirements`, שניהם בקריאה; `fit_score_from_requirements`
  ו-החוזה שלה (1.0 על רשימה ריקה) לא השתנו.
- **D2 — סגור.** ה-short-circuit נמחק. `extraction_failed` הוא בדיוק
  `extraction_state(...) == "unparsed"`.
- **A3 — סגור.** `verify_and_cover_extraction` בונה `Requirement(undetermined)`
  לכל שורה לא-ממופה בעצמה; `unmapped_statements` נשאר גילוי נלווה בלבד.
- **A4 — ההנחה שלו מתקיימת עכשיו בשני הנתיבים.** Stage 2 נחת גם בנתיב ה-AI
  במפורש, ולכן ההפרש בין 1/20 ל-20/20 מיוצג ב-`fit_score`. אין קוד לתקן.
- **A1 — הסיכון השיורי נשאר בדיוק כפי שתואר.** המופע הנוכחי נסגר (שורה שזוהתה
  ולא מופתה נכנסת לניקוד); התלות המעגלית של נתיב ה-AI ב-`requirement_lines()`
  הדטרמיניסטי לא נגעה ולא נפתרה. שורה שהסגמנטר לא מזהה מלכתחילה עדיין
  בלתי-נראית לחלוטין לשני הנתיבים.
- **D3 — נשאר פתוח, כפי שנכתב.** הדנומינטור תוקן; כיול הסף `0.72` לא נגע בו
  אף החלטה שנפתרה.
- **D4-D9 (פרט ל-D2), A2, A5-A11, C1, C2 — ללא שינוי.** שייכים ל-Stage 3-8.

**הצעד הבא:** Stage 3 (`A2`, `A11`) — שני באגים פשוטים בנתיב ה-AI, עצמאיים
מכל מה שנחת כאן.

**החלטות #1-#3 ו-#7-#12 סגורות (RESOLVED)**, כל אחת עם נימוק מלא במקום — ראה
**Open product decisions** למטה. הן מכסות: מה קורה לשורת דרישה שלא מופתה
(#1), למה אין ratio threshold ל-extraction_failed (#2), הסרת understood_elsewhere
ממנו (#3), reason חדש `requirements-absent` על רשימה ריקה (#7), רשומות היסטוריות
לא נוגעים בהן (#8), פרמטר מפורש `requirements_absent` ל-rebase_requirements
במקום גזירה פנימית (#9), `mandatory=False` קבוע לישויות undetermined סינתטיות
עם הנימוק המלא מול D9 (#10), discriminant נפרד למניעת התנגשות ordinal (#11),
ו-reason חדש שני `requirements-unmapped` (#12).

**תוכנית הקבצים ל-Stage 1+2 מאושרת ומוכנה ליישום** — ראה "Stage 1+2 —
implementation file plan" למטה, שבע קבצים בסדר עריכה מוגדר, עם הפניה לכל
החלטה שמצדיקה כל צעד.

**#4-#6 נשארות פתוחות ולא חוסמות** את Stage 1 — הן שייכות לשלבים מאוחרים
יותר (#4→Stage 7, #5→Stage 5/D8, #6→Stage 5/C1) ולא צריך להכריע בהן כדי
להתחיל לממש את Stage 1+2.

**#4-#6 עדיין פתוחות גם אחרי היישום** — Stage 1+2 לא הכריע בהן ולא נגע בהן.

## פריטי מעקב שנפתחו ביישום (לא לתיקון עכשיו)

1. **מודעה קצרה שבאמת לא מציבה דרישות חוסמת מעתה הפקת מסמך.**
   `requirements-absent` הוא `ANALYSIS_INCOMPLETE`, ולכן
   `drafts/generation.py` מסרב עד `apply_analysis_decisions(
   accept_incomplete_analysis=True)`. זו ההתנהגות המכוונת לפי החלטה #7 — עדיף
   שהמשתמש יאשר במפורש "המנוע לא קרא דרישות" מאשר שיקבל `fit=HIGH` שקרי — אבל
   היא הופכת כל מודעה דלילה לשני צעדים במקום אחד. **מדד להחלטה:** אם מודעות
   אמת ללא בלוק דרישות מתבררות כשכיחות, זה חיכוך יומיומי ששווה לשקול מחדש
   (למשל reason שאינו חוסם generation, או סף מבוסס-אורך). לא לפעולה עכשיו.
   נצפה לראשונה בתשעה טסטים ב-`tests/test_ai_tasks.py` שעברו דרך
   `ACCOUNT_MANAGER_JOB` בדרך ל-drafting.
2. **`undetermined_requirement()` לא קובעת `.extractor`** (נשאר `None`, כמו
   בנתיב הדטרמיניסטי). ר' ההערה בסוף החלטה #11 — להשוות כש-Stage 3 נוגע
   ב-`correct_interpretation`.
3. **`mandatory` של ישות סינתטית** — לשקול מחדש מעבר ל-`line.section ==
   "requirements"` אחרי ש-D9 מתוקן (Stage 6). ר' החלטה #10.
4. **D7 מתחיל לזוז.** `concept_classification_completeness` כבר לא קבוע 1.0
   מתמטית ברגע שקיימות ישויות עם `concept=None`. ר' "משנים משמעות" למטה.

## Root cause, restated precisely

Two different denominators are computed from the same job text and never reconciled:

- `fit_score`'s denominator is `len(requirements)` — the list `extract_requirements` /
  `verify_and_cover_extraction` actually managed to turn into a `Requirement` object
  ([gaps.py:62-70](../cv_engine/domain/analysis/gaps.py#L62-L70)).
- `confidence`'s denominator is `len(requirement_lines(text))` — every statement
  `segmentation.py` *thinks* asks something of the candidate
  ([confidence.py:42-45](../cv_engine/domain/analysis/requirements/confidence.py#L42-L45)).

A requirement-bearing statement that the concept vocabulary cannot pattern-match never
becomes a `Requirement(coverage="undetermined")`. It simply does not exist in the first
list. It still exists in the second list, so it costs `confidence` — but it costs
`fit_score` nothing, because `fit_score` never saw it. The only circuit-breaker meant to
catch this, `extraction_failed`, is itself gameable in two independent ways (D1; D2,
including its `understood_elsewhere` short-circuit) and is never even computed for the
AI path's own confidence (A2).

Everything below is a specific way this general shape manifests.

**Status update — decisions #1-#3 resolved.** See **Open product decisions** below.
`D1` and `D2` now close directly in Stage 1 from those resolutions. `A4` — originally
counted here as a fourth way `extraction_failed` was gameable — turned out not to be
one: once `Requirement(coverage="undetermined")` entries exist (decision #1, landed in
Stage 2), `fit_score` itself is what should distinguish a 1-of-20 read from a 20-of-20
read; `extraction_is_failed`'s `any()`-based check was always the right shape for a
purely catastrophic-failure signal (decision #2). The bug was in this document's
original framing of A4, not in the code — see its row in the findings table.

## Fix order

Findings are grouped into stages. A stage should land, and its own focused tests pass,
before the next stage is attempted — per this repo's stage-gate rule (one stage per
session/PR, gates scoped to the affected frontend/backend behavior at delivery;
no automatic full suite). Within a stage, order is not significant.

### Stage 0 — Product decisions: RESOLVED

Decisions #1-#3 (see **Open product decisions** at the end) are resolved. Stage 1 can
be coded against them. Decisions #4-#6 remain open but do **not** block Stage 1 — they
govern later stages only (#4 → Stage 7, #5 → Stage 5/D8, #6 → Stage 5/C1).

### Stage 1 — Root: failure detection is too permissive (both paths)

`D1`, `D2` — plus a **reclassification** of `A4` (not an independent fix; see its
findings-table row). Concretely, against resolved decisions #1-#3:

- **D1 — revised design (supersedes the earlier "`fit_score_from_requirements` returns
  `None`" framing; `gaps.py` is not touched at all):** the `None`-override happens at
  the *call site* — `classify_job` / `rebase_requirements` — exactly where the
  `failed_extraction` override already happens, not inside
  `fit_score_from_requirements` itself. Concretely:
  `fit_score = None if (failed_extraction or not requirements) else
  fit_score_from_requirements(requirements)`. This relies on an invariant Stage 2
  establishes and Stage 1 depends on shipping together with it: once decision #1's
  undetermined-splicing is in place, `requirements == []` becomes possible **only**
  when `requirement_lines(text) == []` (state `"absent"`) — any non-absent state now
  produces at least one `Requirement` (matched, undetermined, partial, or
  unsupported) per line found, so an empty `requirements` list and `state=="absent"`
  become logically equivalent, and checking `not requirements` is exactly checking
  "absent" without needing to import/call `extraction_state` a second time at the
  call site. `fit_score_from_requirements`'s own contract (`1.0` on an empty list —
  "nothing demanded, nothing missing") stays **completely unchanged**, still correct
  in isolation; the call sites simply stop invoking it in the one case where that
  answer would be presented as more certain than it is. **Approval reason:** since
  this path bypasses `failed_extraction` (which is what triggers the
  `"extraction-failed"` reason), a *new* reason is required — see resolved decision
  #7 below (`"requirements-absent"`). **Side effect to carry into review, not a new
  open decision** (directed, not re-opened): a posting that truly states no
  requirements now also reports `fit=UNKNOWN` instead of the old `fit=HIGH` — the
  "not punished for being short" reading gaps.py's docstring describes no longer
  applies until some future signal can independently attest a posting was read in
  full and asks nothing. It is, however, now accompanied by an explicit
  `"requirements-absent"` approval reason (decision #7) rather than silently
  presenting `UNKNOWN` with nothing for the user to act on.
- **D2**: delete the `if understood_elsewhere: return False` short-circuit in
  `extraction_failed` (confidence.py:94-95) entirely, per decision #3.
  `extraction_failed` becomes exactly `extraction_state(...) == "unparsed"` — full stop,
  no rule-gap override.
- **A4 is not fixed here.** See its table row: once decision #1 lands (Stage 2, **in
  both paths**), the difference between reading 1 of 20 requirements and reading 20 of
  20 is carried by `fit_score` (near-zero vs. high, via `undetermined` entries), not by
  the `extraction_is_failed`/`extraction_failed` boolean. `any()`-based
  catastrophic-only detection was always the right shape for that boolean per decision
  #2 — this document's earlier framing of A4 as needing a proportional threshold was
  itself the error, not the code.

**Stage 2 must follow immediately, in the same delivery — not a separately schedulable
stage.** Landing Stage 1 alone opens a window where partial extraction is represented
*nowhere*: not in the boolean (`extraction_failed` is `False` by design, per decisions
#2/#3, for any non-catastrophic case — including a 1-of-20 read), and not in
`requirements` (decision #1's `undetermined` entries don't exist until Stage 2 ships).
A deploy that ships Stage 1 without Stage 2 regresses to a *quieter* version of the
exact bug this document is about: `fit_score` would still be computed from a
`requirements` list containing only the matched items (1 of 20), unpunished, with no
`extraction_failed` signal left to catch it either — Stage 1 alone removes the D1/D2
false-greens but reopens the identical shape one level down. Treat Stage 1+2 as one
PR/session, not two.

### Stage 2 — Denominator unification (decision #1, resolved YES — implements it)

`D3`, `A1`, `A3` — this stage is decision #1's implementation: unmatched
requirement-bearing text (deterministic) and `unmapped_statements` (AI) both need to
enter the same list `fit_score` reads, at zero credit.

**Explicit condition — decision #1 must land in both paths, in the same change.** In
the AI path this means `verify_and_cover_extraction` (ai_extraction.py) itself
constructs a `Requirement(coverage="undetermined", concept=None, ...)` for every
`requirement_line` that no proposed requirement's `attestation` span touches — not
merely preserving the provider's self-reported `unmapped_statements` off to the side
(that remains useful as a *disclosed reason*, A3's own fix, but must stop being the
*only* representation). Without this, A4's reclassification above is false for
AI-derived analyses specifically: a provider that reads 1 of 20 requirements and stays
silent about the other 19 (no `unmapped_statements` entries, or entries nothing
downstream reads — the pre-fix state of A3) would still show `requirements` of length
1, `fit_score` computed only over that 1 — exactly the false-green Stage 1+2 exists to
close, just relocated to the AI path. The deterministic and AI implementations of
decision #1 are two separate code changes (different call sites: `cover_requirements`/
`classify_job` vs. `verify_and_cover_extraction`), and both must ship together for A4's
reclassification to hold in both paths, not only the deterministic one.

**A1 — תיקון חלקי בלבד, סיכון שיורי.** תיקון הסגמנטר (למשל השלמת
`requirement_block_markers`, או המרת שורה שזוהתה-אך-לא-מופתה ל-`undetermined` לפי
החלטה #1) סוגר את *המופע הנוכחי* של A1 — התרחיש הספציפי שבו "What we're looking
for" לא הכיר. הוא **לא** סוגר את התלות המעגלית עצמה: `by_ai`
([ai_extraction.py:557-562](../cv_engine/domain/analysis/requirements/ai_extraction.py#L557-L562))
ו-`extraction_is_failed`
([ai_extraction.py:580-582](../cv_engine/domain/analysis/requirements/ai_extraction.py#L580-L582))
ימשיכו, גם אחרי התיקון, להימדד מול הפלט של אותו `requirement_lines()` דטרמיניסטי —
לא מול מה שה-AI עצמו קרא. כל שורה עתידית שה-segmentation לא יזהה (ניסוח חדש, שפה
שלישית, כותרת לא-צפויה) תישאר בלתי-נראית לחלוטין למדדי ה-AI, ללא קשר לאיכות ה-AI
עצמו — כי אין לנתיב ה-AI שום מדד עצמאי שלא עובר דרך פונקציית הסגמנטציה
הדטרמיניסטית. זהו סיכון מבני קבוע, לא תקלה חד-פעמית שנסגרת ב-Stage 2.

### Stage 3 — AI-path bookkeeping bugs (independent of Stage 0-2)

`A2`, `A11` — these are plain bugs (a missing recompute call; a hardcoded `ordinal=0`),
not policy questions. Can be fixed in any order relative to the other stages, but
listed here because A2 in particular changes what "confidence" means for every AI
analysis and should not be re-tuned twice.

### Stage 4 — Measurement granularity (independent)

`D4` — one bullet, several distinct asks, counted as one unit of "understood."
Independent of denominator unification; fixes a different kind of undercounting.

### Stage 5 — Confidence-formula correctness (depends on Stage 1-4 landing — retuning a
formula before its inputs are trustworthy is wasted work)

`D8`, `C1` — `classification_confidence` measuring a signal (vocabulary) other than the
one that actually decided (coverage), and the one approval reason that *did* fire
(`low-confidence`) being clearable by an override that doesn't address its actual cause
when the cause is extraction rather than classification.

### Stage 6 — Deterministic extraction ordering bugs (independent of everything above)

`D5`, `D6`, `D9` — dedup-before-mandatory-computed; a shared clause letting a nearby
"advantage" demote an explicit "must have" match; and a bare (no-colon) heading that
doesn't match a configured marker silently failing to close whatever section was open,
letting later bullets inherit `section=="requirements"` — and with it `mandatory=True`
— with no marker of their own.

### Stage 7 — AI interpretation/attestation gate integrity (independent domain)

`A5`, `A6`, `A7`, `A9`, `A10`, `A8` — these are about whether the *gate* can be
satisfied by a claim the source text doesn't support, not about scoring arithmetic.
Grouped last only because they require the most product judgment (how strict should a
gate be before it starts rejecting good-faith provider output — see decision #2).

### Stage 8 — Cleanup (do last; no behavior depends on these)

`D7`, `C2` — a completeness sub-score that is a mathematical constant under every
current code path, and a dedup check whose two sides can never produce equal strings.

---

## Findings table

| id | חומרה | קבצים (file:line) | תרחיש הכשל | תלות | סטטוס אימות |
|----|--------|---------------------|--------------|------|----------------|
| **D1** | קריטי — ירוק מלא, 0 approval reasons | [confidence.py:42-45,66-68,96](../cv_engine/domain/analysis/requirements/confidence.py#L42-L96), [gaps.py:62-63](../cv_engine/domain/analysis/gaps.py#L62-L63) | `requirement_lines(text)==[]` → `extraction_completeness` returns `None` → state `"absent"` (not `"unparsed"`) → `extraction_failed` returns `False` (only checks `state=="unparsed"`) → `fit_score_from_requirements([])==1.0` | שורש; Stage 1, **עצמאי מהחלטה #1** (זה שינוי ל-`fit_score_from_requirements` עצמה, לא ל-`requirements` שהיא מקבלת). **תיקון:** תחזיר `None`, לא `1.0`, על רשימה ריקה — ר' פירוט ב-Stage 1 למעלה, כולל תופעת-הלוואי על משרות ריקות-דרישות באמת | **CONFIRMED** — קראתי כל שרשרת הקריאות; ההתנהגות תואמת בדיוק את התיאור, כולל ההודאה בדוקסטרינג של gaps.py:53-60 שהמנגנון סומך על `extraction_failed` להבחין בין "אין דרישות בכלל" ל"דרישות שלא זוהו". ההבחנה הזו לא קיימת בפועל: `extraction_failed` (confidence.py:96) בודק אך ורק `state=="unparsed"`; `state=="absent"` (0 שורות זוהו) עובר תמיד כ-`False`, בלי שום דרך להבדיל "משרה שבאמת לא מציבה דרישות" מ"משרה שהסגמנטר פשוט לא זיהה בה אף שורת דרישה". |
| **D2** | גבוה — extraction_failed מנוטרל ע"י gap-כלל יחיד | [classification.py:441-444](../cv_engine/domain/analysis/classification.py#L441-L444), [confidence.py:94-95](../cv_engine/domain/analysis/requirements/confidence.py#L94-L95), [gaps.py:262-270](../cv_engine/domain/analysis/gaps.py#L262-L270) | `understood_elsewhere=bool(rule_gaps)` → `if understood_elsewhere: return False` **לפני** even בדיקת ה-state — כלומר גם `state=="unparsed"` (שורות זוהו, 0 הובנו, לא רק "absent") מנוטרל | שורש; Stage 1. **תיקון (החלטה #3 RESOLVED):** מחיקת ה-short-circuit לגמרי; `understood_elsewhere` נשאר קלט ל-`extraction_confidence` בלבד (רצפת 0.4) | **CONFIRMED, והיקף רחב מהמתואר**: קראתי `confidence.py:94-96` — ה-short-circuit קורה *לפני* חישוב ה-state בכלל, כך שהבאג לא מוגבל למקרה "0 requirements" (כפי שהדוגמה המקורית תיארה) אלא לכל מקרה שבו נמצא ולו gap-כלל אחד (salesforce/crm/saas/partnership/years-threshold) — גם אם 20 שורות דרישה זוהו ואף אחת לא הובנה. |
| **D3** | גבוה — סף האישור עובר בקריאה חלקית | [approval.py:14](../cv_engine/domain/analysis/approval.py#L14), [confidence.py:99-123](../cv_engine/domain/analysis/requirements/confidence.py#L99-L123), [classification.py:153-168,450-454](../cv_engine/domain/analysis/classification.py#L153-L168) | עם `classified=1.0` (ר' D7) והנוסחה `(0.4+0.6·completeness)·classified`, מספיק `completeness≈0.56` כדי לחצות `0.72/0.98≈0.735` | Stage 1+2 (החלטה #1 **RESOLVED=YES**) — אך הסף `0.72` עצמו לא מושפע מהחלטות #1-#3 (אלה קבעו *איך* partial extraction מיוצג, לא *מה הסף* לאישור על ייצוג כזה); D3 נשאר שאלת כיול פתוחה, לא מכוסה ע"י אף החלטה שנפתרה | **CONFIRMED** — שחזרתי את החשבון ישירות מהנוסחאות; מספרי הדוגמה (0.735, c≥0.558) עקביים עם קריאת הקוד, בהנחת `classification_confidence` גבוה טיפוסי. |
| **D4** | בינוני-גבוה — בולט עם 3 בקשות נספר כיחידת "הבנה" אחת | [confidence.py:14-25](../cv_engine/domain/analysis/requirements/confidence.py#L14-L25), [extraction.py:118-167](../cv_engine/domain/analysis/requirements/extraction.py#L118-L167), [segmentation.py:241](../cv_engine/domain/analysis/requirements/segmentation.py#L241) | `_understood` בודק חפיפת offset בין ה-`StatementLine` המלא (כל המשפט) לבין ה-`ExtractedRequirement.span` שהוא רק תת-מחרוזת שהרג'קס תפס — משפט אחד ארוך עם 3 דרישות, רק 1 חולצה, נספר כ"מובן" במלואו | עצמאי | **CONFIRMED** — `item.start`/`item.end` הם offsets של ה-regex match בלבד (extraction.py:141-165), לא של המשפט; `_understood` (confidence.py:21-25) סופר overlap ברמת ה-line, לא ברמת המושג. `segmentation.py:241` מוסיף אפקט נלווה: שורה שממשיכה משפט קודם (lowercase, ללא bullet) ממוזגת לאותה יחידה. |
| **D5** | גבוה — dedup קובע mandatory/preferred לפי המופע הראשון | [extraction.py:132-147](../cv_engine/domain/analysis/requirements/extraction.py#L132-L147), [requirements.json:43-68](../config/requirements.json#L43-L68) | דה-דופ (שורה 132-136, `concept`+`demanded`) רץ **לפני** חישוב mandatory/preferred (שורה 147) → אזכור ראשון תחת "About us" (preferred) "בולע" את המופע השני תחת "Requirements:" (mandatory) | עצמאי | **CONFIRMED, עם תנאי מוקדם שאומת**: cue-word matching ב-`_statement_kind` ([segmentation.py:169-171](../cv_engine/domain/analysis/requirements/segmentation.py#L169-L171)) הוא **ללא תלות בסקשן** — מילה כמו "experience" (ברשימת `requirement_cues`, config:51) בפסקת "About us" גם היא מסמנת את המשפט כ-`kind="requirement"`, ולכן נכנס בכלל למנוע ה-extraction (extraction.py:111: `if span.kind != "requirement": continue`). זה מה שהופך את התרחיש לריאלי, לא תיאורטי בלבד. |
| **D6** | גבוה — clause משותף מאפשר ל"advantage" סמוך לבטל "must have" מפורש | [extraction.py:20,57-80,140,147](../cv_engine/domain/analysis/requirements/extraction.py#L20-L147) | `_SENTENCE=[.;\n]` לא חותך על פסיק; "Must have 5+ years..., European market an advantage." — אין parenthetical, אז ה-clause הוא כל המשפט; `"advantage"∈preferred_markers` (config:36) הופך את **כל** ה-clause, כולל ה-5+ שנים, ל-preferred | עצמאי | **CONFIRMED** ישירות מהרג'קס והקונפיג — `_SENTENCE` אינו כולל פסיק, ו-`_clause_around` (extraction.py:57-80) מחזיר את המשפט השלם פחות parentheticals כש-ה-match אינו בתוך aside. אותה א-סימטריה חוזרת ב-[interpretation.py:58-61](../cv_engine/domain/analysis/requirements/interpretation.py#L58-L61) בנתיב ה-AI, על ה-quote המצוטט. |
| **D9** | גבוה — כותרת ללא נקודתיים לא סוגרת section, בולט הטבות יורש `mandatory=True` | [segmentation.py:96-120](../cv_engine/domain/analysis/requirements/segmentation.py#L96-L120) (`_heading_section`), [segmentation.py:123-142](../cv_engine/domain/analysis/requirements/segmentation.py#L123-L142) (`_section_of`), [extraction.py:147](../cv_engine/domain/analysis/requirements/extraction.py#L147) | כותרת כמו "Perks"/"Benefits" (בלי `:`) שאינה matches מדויק לאף marker מוגדר מחזירה `None` מ-`_heading_section`; `None` לא סוגר section פתוח (רק heading לא-`None` משנה `section`) → הbulletים שתחתיה יורשים את ה-section הקודם. אם זה "requirements", בולט הטבות תמים שמזדמן להתאים ל-concept pattern מקבל `mandatory=True` ב-extraction.py:147 בלי אף מרקר | עצמאי; שלב 6 עם D5/D6 | **CONFIRMED** — עקבתי את `_segments` (segmentation.py:181-248) שורה-שורה: `section` משתנה רק ב-`if heading is not None: ...; section=heading` (שורה 219-226); heading=`None` פשוט `continue`-ת בלי לגעת ב-section. אין קוד שסוגר section על heading לא-מזוהה. |
| **D7** | בינוני — מדד מת, קבוע 1.0 בכל נתיב קיים | [confidence.py:48-57](../cv_engine/domain/analysis/requirements/confidence.py#L48-L57), [extraction.py:148-166](../cv_engine/domain/analysis/requirements/extraction.py#L148-L166) | `concept_classification_completeness` סופר `item.concept` לא-ריק; כל `ExtractedRequirement` נבנה תמיד עם `concept=concept.concept` (מחרוזת לא ריקה) — אין היום שום נתיב מייצר item ללא concept | Stage 8 (cleanup; ייתכן ותלוי בהחלטה #1 אם ייווצר נתיב חדש) | **CONFIRMED** — grep/read מלא של extraction.py לא מצא בנאי `ExtractedRequirement` עם `concept=""`/`None`. המדד קבוע מתמטית בקוד הנוכחי. |
| **D8** | בינוני — confidence מודד וקטור שלא קיבל את ההחלטה | [classification.py:336-348,414-418,453-454](../cv_engine/domain/analysis/classification.py#L336-L454) | הבחירה בפועל (`best()`) מדורגת לפי `(coverage_scores, term_scores)` — coverage קודם; אבל `top`/`second` שמוזנים ל-`classification_confidence` מגיעים אך ורק מ-`term_scores.most_common(2)` (שורה 416-418), בלי קשר ל-coverage | Stage 5 (אחרי שהדנומינטורים מתוקנים) | **CONFIRMED** — קראתי את כל `classify_job`; `ranking` (משמש להחלטה ול-ambiguity) ו-`top/second` (משמש ל-confidence) הם שני חישובים נפרדים לחלוטין מאותו טקסט. |
| **A1** | קריטי — נתיב AI לא יכול לגלות את באג הסגמנטציה | [analysis.py:234-241](../cv_engine/application/services/analysis.py#L234-L241), [ai_extraction.py:557-562,580-582](../cv_engine/domain/analysis/requirements/ai_extraction.py#L557-L582) | הספק מקבל `requirement_lines(job_text,...)` כ-hint; `by_ai` (understanding) ו-`extraction_is_failed` נמדדים מול **אותה** `requirement_lines()` — שורה שהסגמנטר לא מזהה (למשל תחת כותרת לא ב-`requirement_block_markers`) לא יכולה להוריד את `by_ai`, לא תדליק כשל, ולא תופיע כפער בשום מקום | Stage 1+2 (החלטות #1-#3 **RESOLVED**), עם תנאי מפורש ש-Stage 2 מיושם בנתיב ה-AI עצמו (ר' Stage 2 למעלה) — הסיכון השיורי (סגמנטציה שלא מזהה שורה מלכתחילה) נשאר גם אז, ר' Stage 2 | **CONFIRMED** — אימתתי את כל שלוש נקודות הקריאה; אין שום נתיב אחר ב-ai_extraction.py שממדל את הטקסט המלא ללא תלות ב-`requirement_lines`. |
| **A2** | גבוה — confidence לא מחושב מחדש אחרי rebase | [classification.py:221-305](../cv_engine/domain/analysis/classification.py#L221-L305) (`rebase_requirements`), [analysis.py:280-295](../cv_engine/application/services/analysis.py#L280-L295) | `rebase_requirements`'s `model_copy(update={...})` מעדכן requirements/gaps/fit/fit_score/approval_reasons — **לא** confidence; לאחר מכן `merge_classification` עושה `min(deterministic.confidence, proposal.confidence)` על אותו confidence-לא-מעודכן | עצמאי (Stage 3) | **CONFIRMED** — קראתי את מילון ה-`update=` המלא ב-rebase_requirements (classification.py:289-304): אין מפתח `confidence`. עקבתי את הזרימה המלאה ב-analysis.py:280-328 — אין קריאה חוזרת ל-`extraction_confidence` אחרי rebase בשום מקום. |
| **A3** | גבוה — unmapped_statements נאסף, מאומת, ולא נקרא ע"י אף לוגיקת ניקוד | [ai_extraction.py:309-323,543-554](../cv_engine/domain/analysis/requirements/ai_extraction.py#L309-L554), [approval.py:197](../cv_engine/domain/analysis/approval.py#L197) | `unmapped_statement_ids()` מוגדרת ואף פעם לא נקראת (grep מלא בכל הפרויקט); `analysis.unmapped_statements` רק "עובר דרך" ב-merge_classification, לא נבדק ע"י שום approval reason או חישוב fit/confidence | Stage 2 (החלטה #1 **RESOLVED=YES**) — התיקון *הוא* חיווט זה, בתנאי המפורש שנוסף ל-Stage 2: `verify_and_cover_extraction` עצמה בונה `Requirement(undetermined)` לכל שורה לא-ממופה, לא רק שומרת unmapped_statements בצד | **CONFIRMED via grep**: `grep -rn "unmapped_statement_ids"` מחזיר רק את שורת ההגדרה. `grep -rn "\.unmapped_statements"` מחזיר רק "pass-through" ב-approval.py ו-האיסוף עצמו ב-ai_extraction.py — אין קורא שלישי. |
| **A4** | **מוגדר-מחדש — לא באג עצמאי.** הממצא המקורי (וההגדרה שלו כ"שורש") היה שגוי, לא הקוד | [ai_extraction.py:567-593](../cv_engine/domain/analysis/requirements/ai_extraction.py#L567-L593) | `return not any(...)` — מיפוי מוצלח של שורה אחת מתוך N מונע `extraction_is_failed`, גם אם N=20. **זו ההתנהגות הנכונה לפי החלטה #2** (בוליאני לכשל קטסטרופלי בלבד, לא מדד שלמות); ההבדל בין 1/20 ל-20/20 אמור להיות מיוצג ב-`fit_score` (דרך `undetermined` requirements, החלטה #1), לא בבוליאני הזה | **תלוי Stage 1+2 בשני הנתיבים** (ר' התנאי המפורש ב-Stage 2 למעלה) — עד ש-Stage 2 נוחת בנתיב ה-AI במפורש (לא רק הדטרמיניסטי), ה-1/20 עדיין בלתי-מיוצג שם לגמרי, וזה עדיין false-green בפועל — רק שהוא כבר לא "A4 צריך תיקון", אלא "Stage 2 טרם נחת בנתיב ה-AI" | **CONFIRMED שהקוד עושה בדיוק את זה** (`any()` ללא סף יחס) — **אך התיקון המוצע בגרסה הקודמת של המסמך (סף יחס) שגוי**; אין צורך בו, ר' החלטה #2 RESOLVED וההסבר ב-Stage 1. |
| **A5** | גבוה — demanded/kind מהספק לא מאומתים מול הציטוט | [ai_extraction.py:265-280](../cv_engine/domain/analysis/requirements/ai_extraction.py#L265-L280), [interpretation.py](../cv_engine/domain/analysis/requirements/interpretation.py) (כל הקובץ) | `cover_ai_requirement` מזין `demanded=demanded` (מהספק) ישירות ל-`threshold_coverage`; `verify_interpretation` בודק source_role/obligation/composition/members/negation — **לא** `demanded`, לא `kind` | Stage 7 | **CONFIRMED**: קראתי את כל `interpretation.py` — אין שום אזכור של `demanded` או `kind` בקובץ. ציטוט מאומת בת-byte של "10+ years" עם `demanded="2"` שנשלח ע"י הספק יעבור ללא בדיקה. |
| **A6** | גבוה — שער חד-כיווני: אפשר לרומם ל-requirement, אי אפשר להכחיש | [interpretation.py:52-71](../cv_engine/domain/analysis/requirements/interpretation.py#L52-L71) | הלולאה (שורה 54-56) בודקת רק "אם ה-section אומר mandatory/preferred, אסור לסתור" — לציטוט מ-section `"other"` (בלוק הטבות) שני התנאים (`preferred`, `mandatory`) הם `False`, אז שום exception לא נזרק, ללא קשר למה שהספק הצהיר | Stage 7 | **CONFIRMED** ישירות מהלוגיקה — עקבתי את שני ה-if-ים; אף אחד לא תלוי ב-`interpretation.source_role`/`obligation` כשה-section הוא `"other"`. הבדיקה בשורות 87-96 (`obligation=="mandatory" and source_role!="requirement"`) גם לא תופסת את המקרה כי היא דורשת אי-התאמה בין obligation ל-source_role, לא בין source_role לתוכן בפועל. |
| **A7** | בינוני — ציטוט שחוצה גבול-statement מדלג על הבדיקה בשקט | [interpretation.py:52-56,175-195](../cv_engine/domain/analysis/requirements/interpretation.py#L52-L195) | `for statement in _segments(...): if not (contained): continue` — אם אף statement לא מכיל את הספן במלואו, הלולאה מסתיימת בלי לבדוק דבר (לא raise, לא flag) | Stage 7 | **CONFIRMED** — קראתי את הלולאה; אין `else`/fallback אחרי שהלולאה מסתיימת ללא match. אימתתי גם את האי-עקביות מול `_same_statement` (שורה 190-195) שמשתמשת בחפיפה (overlap) ולא בהכלה (containment) — שתי פונקציות שונות לאותה שאלה. |
| **A8** | בינוני — דרישת ייחודיות ל-context_quote מתנגשת עם הנחיית הפרומפט עצמו | [interpretation.py:130-156](../cv_engine/domain/analysis/requirements/interpretation.py#L130-L156), [system-v3.md:27-28](../ai/prompts/system-v3.md#L27-L28) | הפרומפט מנחה: "unless you quote an explicit mandatory marker ('must','required','חובה') in context_quote"; ה-gate דוחה `context_quote` שמופיע יותר מפעם אחת בטקסט המלא — מילים כמו "must"/"required" חוזרות כמעט תמיד במודעת עבודה אמיתית | Stage 7 | **CONFIRMED**: קראתי את `system-v3.md` ואת `_verify_context_quote_occurs` (interpretation.py:148-156, `source_text.find(quote, first+1) != -1` → raise). זו סתירה מובנית בין ההנחיה לספק לבין המדיניות שאוכפת אותה, לא תלוית-תרחיש ספציפי. |
| **A9** | בינוני — any-of: חבר חלש-משמעות מנצח את הדרישה כולה | [ai_extraction.py:209-237](../cv_engine/domain/analysis/requirements/ai_extraction.py#L209-L237) | `"matched" if "matched" in member_coverages"` — אין בדיקה שהחבר שהתאים הוא זה שנושא את עיקר הדרישה | Stage 7 | **CONFIRMED** ישירות מהקוד. |
| **A10** | בינוני — כיוון הפוך: ≥2 concepts תואמים ⇒ undetermined, גם בציטוט "טבעי" | [ai_extraction.py:56-71](../cv_engine/domain/analysis/requirements/ai_extraction.py#L56-L71) | `concept_for_quote` מחזיר `None` (⇒ undetermined) כש-יותר מקונספט אחד תואם — בולט שלם עם 3 מושגים (בדיוק מה שהפרומפט מבקש לצטט) נופל תמיד | Stage 7 | **CONFIRMED** ישירות מהקוד — `matches[0] if len(matches)==1 else None`. |
| **A11** | גבוה — ordinal=0 קבוע ⇒ ID כפול ⇒ ניפוח מכנה | [ai_extraction.py:520-528](../cv_engine/domain/analysis/requirements/ai_extraction.py#L520-L528) | `ordinal=0` בכל שורה; `requirement_id` נבנה מ-hash של interpretation+kind+demanded+identity_span+ordinal — הצעה כפולה (אותו quote+interpretation) מייצרת שני `Requirement` שונים ברשימה עם **אותו** requirement_id, בלי דה-דופ | Stage 3 | **CONFIRMED** — קראתי את `verify_and_cover_extraction`: אין שום בדיקת ייחודיות על `req_id`/span לפני `requirements.append(...)`. |
| **C1** | בינוני — האזהרה שכן נדלקה (low-confidence) ניתנת לביטול בטעות | [approval.py:52-76](../cv_engine/domain/analysis/approval.py#L52-L76) | `"low-confidence": ApprovalReason(frozenset({"track","profile"}), ...)` — בחירת Profile מנקה אזהרת confidence נמוך גם כשהסיבה האמיתית היא extraction_score נמוך, לא classification | Stage 5 | **CONFIRMED** מהטבלה עצמה — ואימתתי שההערה הפנימית בקוד (שורות 65-67) חלה ניסוחית בדיוק על `extraction-failed` בלבד, לא הורחבה ל-`low-confidence` שסובל מאותה בעיה. |
| **C2** | בינוני — dedup בין rule-gap ל-requirement-gap כמעט אף פעם לא תואם | [classification.py:461-465](../cv_engine/domain/analysis/classification.py#L461-L465) | `covered_text = {requirement.text ...}` מול `gap.requirement` (תווית כתובה ביד כמו `"Salesforce"`, `"Direct SaaS Sales preference"`) — אין קונספט בשם salesforce/saas ב-`requirements.json`, כך שהמחרוזות האלה לעולם לא ייווצרו כ-`requirement.text` | Stage 8 | **CONFIRMED**: סרקתי את כל `config/requirements.json` — אין concept בשם salesforce/saas; המחרוזות היחידות שיכולות להגיע ל-`requirement.text` הן span-ים שחולצו מהטקסט (via `item.span`/`normalize_span`), לא התוויות הקבועות מ-`derive_gaps`. |

---

## בדיקות אדומות לכל ממצא

לכל ממצא: קלט קונקרטי, הערך הצפוי (מה שהמערכת *אמורה* להחזיר לפי הכוונה המוצהרת
בקוד/בדוקסטרינג), והערך שמתקבל היום בפועל. רוב הבדיקות הן קטע טקסט משרה שעובר דרך
`classify_job`. כשמדובר בבאג שדורש שני שלבים (deterministic → AI rebase) או פרופוזל
מדומה מספק, זה כתוב במפורש — אלה עדיין טסטים יחידה תקינים, רק לא מסוג "טקסט משרה
יחיד", ומצוין למה.

### D1
שני קלטים: העברי מדגים את החמצת הסגמנטציה עצמה (אבל **לא** מפיק `approval_reasons=[]`
— `PROFILE_TERMS`/`SALES_TERMS`/`TECH_TERMS` הם אנגלית בלבד, [classification.py:37-96](../cv_engine/domain/analysis/classification.py#L37-L96),
כך שעל טקסט עברי `top=second=0` תמיד → `classification_confidence(0,0)=0.58<0.72` →
`low-confidence` נדלק ללא קשר למצב ה-extraction). האנגלי מדגים את מצב ה-0-אזהרות
המלא, שדורש גם vocabulary-match חזק וגם requirement_lines ריק בו-זמנית.

**קלט 1 (עברית — מדגים רק את החמצת הסגמנטציה):**
```
אנחנו מחפשים אשת/איש מכירות למשרה מלאה.

מה תעשו:
- ניהול תיק לקוחות קיים
- סגירת עסקאות חדשות

מה חשוב לנו:
• זמינות מיידית למשרה מלאה
• מגורים באזור המרכז
```
"מה חשוב לנו:" אינה ב-`requirement_block_markers`/`mandatory_markers`/`preferred_markers`
→ section="other"; אף אחת מהשורות מכילה cue מרשימת `requirement_cues`/`soft_skill_cues`
(he) → שתי הבולטים מקבלים `kind=None` ונשמטים לגמרי מ-`statement_lines`.
**צפוי (אחרי תיקון D1, Stage 1 — עצמאי מהחלטה #1):** `fit_score=None`, `fit=UNKNOWN` —
`fit_score_from_requirements([])` לא יחזיר יותר `1.0` (ר' Stage 1).
**בפועל (היום):** `requirement_lines(text)==[]` → `fit_score=1.0`, `fit=HIGH`, אבל
`approval_reasons=["low-confidence"]` — **לא** ריק, כי `term_scores` (אוצר מילים
אנגלי בלבד) הוא אפס על טקסט עברי. כלומר: fit=100% המסוכן כבר קיים כאן, אבל התופעה
"0 אזהרות" דורשת קלט שני.

**קלט 2 (אנגלית — מדגים 0 approval reasons בפועל, מאומת שורה-שורה):**
```
Account Executive — Closing New Business

We're hiring an Account Executive to own quota-carrying, new business closing deals.

What we're looking for:
- A natural closer who loves people
- Hungry, proactive, and building your own pipeline
```
`term_scores[ACCOUNT_EXECUTIVE]` סופר "account executive"(×2)+"closing"(×2)+"quota"(×1)+
"new business"(×2) = 7 (config: [classification.py:58](../cv_engine/domain/analysis/classification.py#L58));
שאר הפרופילים בציון 0 → `top=7, second=0` →
`classification_confidence=min(0.98, 0.58+0.56+0.28)=0.98`. אף שורה לא מקבלת `kind`:
הכותרת/הפסקה הפותחת לא מכילות cue, "What we're looking for:" אינה מרקר מוכר (section
נשאר "other"), ושני הבוליטים ("natural closer"/"loves people"/"Hungry, proactive"/
"building your own pipeline") לא מכילים אף cue מרשימת `requirement_cues` (כולל
`soft_skill_cues` הממוזגת לתוכה, concepts.py:88) → `requirement_lines()==[]`.
"quota-carrying" כן מכיל "quota", אבל הפסקה שמכילה אותו כבר נפסלה (`kind=None`) לפני
שההתאמה ל-concept `quota-attainment` אפילו נבדקת (extraction.py:111 בודק `span.kind`
לפני שהוא בכלל מריץ patterns). אין "years"/מספר בטקסט → אין rule_gap מ-`derive_gaps`.
**צפוי (אחרי תיקון D1, Stage 1 — עצמאי מהחלטה #1):** `fit_score=None`, `fit=UNKNOWN` — גם עם
`confidence=0.98` (הbug של D1 הוא ב-`fit_score`, לא ב-confidence; שים לב ש-confidence
נשאר גבוה גם אחרי התיקון — זו בדיוק הסיבה ששני המספרים מוצגים בנפרד).
**בפועל (היום):** `requirements=[]`, `extraction_confidence=1.0`
(completeness=None→classified=1.0), `confidence=round(1.0·0.98,4)=0.98`,
`failed_extraction=False` (state="absent"), `fit_score=1.0`, `fit=HIGH`,
`approval_reasons=[]` — 0 אזהרות, בדיוק כפי שהתא בטבלה טוען.

### D2
קלט (אנגלית, 3 שורות דרישה אמיתיות שלא ממופות לאף concept, + אזכור "Salesforce" תחת
כותרת בלי נקודתיים):
```
Requirements:
- Excellent time-management and organizational skills
- Strong communication skills
- Comfortable working under pressure

Perks
- We use Salesforce and Slack daily
```
**תיקון חשוב מהגרסה הקודמת של המסמך: `requirement_lines` הוא 4, לא 3.** "Perks" בלי
נקודתיים **אינו** נכנס לענף ה-heading בכלל: `_heading_section` (segmentation.py:96-120)
בודק colon תחילה (`stripped.endswith(":")` → false), ואז — בהיעדר colon — דורש התאמה
מדויקת ל-marker מוגדר דרך `heading_sections.get(heading_key(stripped))`; "perks" אינו
key שם → מחזיר `None`. `None` heading לא סוגר section (ר' D9 למטה) → ה-section הפתוח
"requirements" (מ-"Requirements:") **ממשיך** דרך שורת "Perks" עצמה (שנשמטת כי קצרה
מ-`_MIN_STATEMENT`) אל תוך הבולט של Salesforce. הבולט הזה, כ-list-item תחת
section=="requirements", מקבל `kind="requirement"` דרך הכלל ב-segmentation.py:172-173
— **גם בלי אף cue** בתוכו. סה"כ 4 requirement_lines: 3 עם cue "skills" + 1 (Salesforce)
דרך ירושת ה-section. אף concept לא תואם אף אחת מה-4 → `extracted=[]` →
`completeness=0/4=0.0` → `state="unparsed"`. `derive_gaps` מזהה "salesforce" ב-lowered
(ללא תלות בסקשן) → `rule_gaps` לא ריק → `understood_elsewhere=True`.
**צפוי (אחרי תיקון D2, החלטה #3 RESOLVED — מחיקת ה-short-circuit):** `extraction_failed=
True` (4 דרישות נאמרו, 0 הובנו) → `fit_score=None`, `fit=UNKNOWN`, `approval_reasons`
כולל `extraction-failed`. `understood_elsewhere` ממשיך להשפיע רק על `extraction_
confidence` (הרצפה 0.4), לא על הבוליאני.
**בפועל (היום):** `confidence.py:94-95` מחזיר `False` לפני שבכלל בודק את ה-state →
`fit_score=fit_score_from_requirements([])=1.0`, `fit=HIGH`, ה-gap היחיד הוא warning
(לא חוסם), confidence≈`0.4×classification_confidence` (נמוך, אך fit עדיין 100%).

### D3
זה נכון יותר לבדוק ברמת הפונקציה הטהורה מאשר טקסט משרה מלא, כי השאלה היא ישירות על
הנוסחה: `extraction_confidence(completeness=0.56, classified=1.0, understood_elsewhere=False)`
מול `classification_confidence(top=5, second=0)`.
**צפוי:** קריאה של 56% מהדרישות לא אמורה לעבור סף אישור של 0.72.
**בפועל:** `(0.4+0.6·0.56)·1.0 = 0.736`; `classification_confidence(5,0)=min(0.98,0.58+0.4)=0.98`;
`round(0.736·0.98,4)=0.7213 ≥ 0.72` → עובר, אפס approval reasons מ-confidence.
(תרחיש טקסט-משרה מלא לאותה נקודה: 9 בוליטים בסגנון D2 שבהם 5 ממופים ותואמים כ-matched —
דורש facts fixture קיים ב-`tests/test_analysis.py`, לא מצוטט כאן כדי לא להמציא fact IDs.)

### D4
קלט:
```
Requirements:
- 5+ years of B2B sales experience, comfortable in a fast-paced startup, and hands-on Salesforce administration.
```
בולט אחד, cue "experience" → `StatementLine` יחיד לכל המשפט. רק "5+ years...sales"
תואם concept (`sales-closing-experience-years`); "fast-paced startup" ו-"Salesforce
administration" לא ממודלים כלל.
**צפוי:** רק חלק מהבקשות בבולט הובנו — ציון השלמות אמור לשקף זאת (למשל לפי-concept, לא
לפי-statement).
**בפועל:** `_understood` בודק חפיפת offset ברמת ה-line השלם → הבולט כולו נספר "מובן
במלואו" (`completeness=1.0`, `state="parsed"`), למרות ש-2 מתוך 3 הבקשות בו לא נקראו כלל.

### D5
קלט:
```
About Us
Our team combines deep sales experience with technical rigor. Full sales cycle exposure is a plus for this role.

Requirements:
- Must own the full sales cycle end to end
```
המשפט הראשון (About Us) מכיל cue "experience" → `kind="requirement"` **למרות שהוא לא
תחת section דרישות** (ר' segmentation.py:169-171 — cue גובר על section, ללא תלות
בכיוון). הוא תואם `full-sales-cycle`, preferred (יש "a plus" בקלוז). הדה-דופ
(extraction.py:132-136, מפתח `concept`+`demanded`) נרשם ראשון. הבולט השני, תחת
"Requirements:", תואם אותו concept באותו `demanded=None` → מדולג לגמרי.
**צפוי:** ל-"Must own the full sales cycle" תחת Requirements: אמורה להיווצר `Requirement`
עם `mandatory=True`.
**בפועל:** נוצר `Requirement` יחיד בלבד לconcept הזה, עם `mandatory=False` — הבולט
המפורש עם "Must" לא קיים ברשימה כלל.

### D6
קלט (משפט אחד, ללא נקודה/פסיקה חוצצת):
```
Requirements:
- Must have 5+ years of B2B sales experience, European market experience is an advantage.
```
`_SENTENCE=[.;\n]` לא חותך על פסיק → הקלוז של "5+ years...sales" הוא המשפט השלם, שמכיל
"advantage" (preferred_markers).
**צפוי:** "Must have 5+ years" מסומן במפורש כ-mandatory.
**בפועל:** `mandatory=False` (הודגם לpreferred) בגלל "advantage" שמתייחס בפועל רק ל-European
market, לא לדרישת השנים.

### D9
שני כיוונים — הבטוח (ניפוח denominator, נראה כבר בדוגמת D2 למעלה: הבולט של Salesforce
תחת "Perks" הופך ל-requirement_line רק כי הסקשן לא נסגר) והמסוכן (mandatory מומצא):

קלט (כיוון מסוכן):
```
Requirements:
- Must have 5+ years of B2B sales experience

Perks
- Native English speakers get an extra paid day off every quarter
- Free gym membership
```
"Perks" (בלי `:`) לא סוגרת את ה-section "requirements" שנפתח ע"י "Requirements:" (ר'
מנגנון בטבלה). הבולט "Native English speakers get an extra paid day off every quarter"
תואם את הפטרן `native english[a-z ]*` (concept `english-proficiency`, `demanded=
"native"`) — לא כי מישהו דרש זאת, אלא כי המשפט על ימי חופש מזדמן להכיל את הצירוף. עם
`span.section=="requirements"` (ירושה) ובלי אף preferred_marker בקלוז:
`mandatory = (not preferred) and (marked or span.section=="requirements") = True`
(extraction.py:147).
**צפוי:** תיאור הטבה (ימי חופש) לא אמור להפוך אף פעם ל-mandatory requirement.
**בפועל:** נוצר `Requirement(concept="english-proficiency", mandatory=True,
demanded="native", ...)` מתוך משפט על הטבות. אם למועמד אין `common.language.english`
ברמת "native" — זה hard gap שחוסם אישור, על דרישה שהמשרה מעולם לא ניסחה.

### D7
לא ניתן לבטא כ-diff של קלט/פלט על טקסט משרה — זהו מדד שקבוע מתמטית תחת כל נתיב קוד קיים,
לא באג שמייצר ערך שגוי על קלט ספציפי. הטסט המתאים הוא assertion מבני: לכל
`ExtractedRequirement` שנוצר ע"י `extract_requirements` (כל קלט), `item.concept` הוא
תמיד מחרוזת לא ריקה (extraction.py:148-166 בונה אותו כך תמיד) → `concept_classification_
completeness(extracted)` שווה 1.0 עבור **כל** קלט לא-ריק. **צפוי מול בפועל:** אין הבדל —
זו הבעיה: אין שום קלט שמזיז את המדד הזה מ-1.0.

### D8
דורש facts/profiles fixture קיים (לא ממציא fact IDs כאן) — התבנית: טקסט משרה עשיר
באוצר מילים טכני ("developer", "software", "API" חוזרים) כך ש-`term_scores` מעדיף
DEVELOPMENT בפער גדול, בעוד שה-Requirements בפועל (שנקבעים ע"י coverage מול facts) 
תומכים חזק יותר ב-ACCOUNT_MANAGER.
**צפוי:** confidence אמור לשקף חוסר-ודאות לגבי ההחלטה שהתקבלה בפועל (coverage-based).
**בפועל:** `top`/`second` מגיעים אך ורק מ-`term_scores` (classification.py:416-418) —
`classification_confidence` מדווח ודאות גבוהה (0.9+) על סמך אוצר מילים שלא הכריע כלום.

### A1
קלט (אנגלית, כותרת לא-מוכרת, בוליטים ללא אף cue):
```
What we're looking for:
- A natural closer who loves working with people
- Hungry, proactive, and comfortable building your own pipeline
```
"What we're looking for:" לא ב-`requirement_block_markers`; אף בולט לא מכיל cue מוכר
("comfortable building" ≠ "comfortable with"). שני הבוליטים מקבלים `kind=None`.
**צפוי:** `requirement_lines()` אמור לכלול את שני הבוליטים (הם דרישות אמיתיות).
**בפועל:** `requirement_lines(text, concepts) == []` — ולכן גם `by_ai`
(ai_extraction.py:557-562) וגם `extraction_is_failed` (ai_extraction.py:580-582) עיוורים
לשתי השורות האלה **ללא קשר למה שה-AI עצמו הציע**, כי שתיהן קוראות לאותה פונקציית
סגמנטציה דטרמיניסטית.

### A2
טסט יחידה טהור על `rebase_requirements` (לא דורש טקסט משרה): בונים `JobAnalysis`
בסיסי עם `confidence=0.9`, קוראים
`rebase_requirements(deterministic, requirements=[], extraction_version="ai:1:1", facts=..., extraction_failed=True)`.
**צפוי:** confidence של תוצאה שה-AI קבע שאין בה אף requirement מאומת (אחרי extraction
דטרמיניסטי "בטוח" ב-0.9) אמור להשתנות/להתעדכן.
**בפועל:** `result.confidence == 0.9` — זהה ל-deterministic, כי מילון ה-`update=` ב-
rebase_requirements (classification.py:289-304) לא כולל מפתח `confidence` כלל.

### A3
טסט יחידה על `extraction_is_failed` (לא דורש טקסט משרה מלא, רק שתי גרסאות פרופוזל):
אותו `requirements=[]`, פעם עם `unmapped_statements=[]` ופעם עם
`unmapped_statements=[UnmappedStatement(text="5+ years of enterprise negotiation
experience", start=.., end=.., reason="no concept")]` על אותו job_text.
**צפוי:** ספק שמצהיר ביושר על דרישה שלא הצליח למפות אמור לקבל תוצאה שונה (למשל gap/
approval reason נפרד) מספק ששותק.
**בפועל:** שתי הקריאות מחזירות `JobAnalysis` זהה ב-fit/confidence/gaps/approval_reasons
— `_unmapped` "מתקבל ומכוון לא נקרא" (ai_extraction.py:575-576), אין קורא שלישי
שמייחס לו משקל (מאומת ב-grep).

### A4 — מוגדר-מחדש, ר' הטבלה
קלט (זהה לגרסה הקודמת):
```
Requirements:
- 5+ years of B2B sales experience
- Native-level English proficiency
- Strong negotiation and closing skills
- Comfortable working from our Tel Aviv office
```
4 requirement_lines (הרביעי נכנס כ-list-item תחת section="requirements", לא דרך cue),
רק הראשון ממופה. **מה שהיה כתוב כאן קודם שגוי:** `extraction_is_failed` המחזיר
`False` (`not any(...)`) **אינו** הבאג — זו בדיוק ההתנהגות הרצויה לפי החלטה #2
(בוליאני לכשל קטסטרופלי בלבד). הטסט האדום האמיתי הוא לא על הבוליאני, אלא על
`requirements`/`fit_score`, ותלוי בשלב:
**צפוי (אחרי Stage 1+2, בשני הנתיבים):** 3 מתוך 4 השורות שלא מופו הופכות ל-
`Requirement(coverage="undetermined")`; `fit_score` יורד משמעותית (רוב ה-denominator
באפס קרדיט) — למרות ש-`extraction_failed=False` נשאר נכון וממשיך להיות `False`.
**בפועל (היום, לפני Stage 1+2):** רק הדרישה הממופה נכנסת ל-`requirements`; 3 האחרות
נעלמות; `fit_score` מחושב על 1 בלבד. זה עדיין הבאג האמיתי בקלט הזה — אבל הוא הבאג של
D1/D3/החלטה #1 (טרם מיושמת בקוד), לא של A4. A4 עצמו, כממצא-בוליאני נפרד, נסגר ע"י
ההבהרה הזו בלי לשנות שורת קוד אחת.

### A5
קלט:
```
Requirements:
- Must have 10+ years of enterprise SaaS sales experience
```
פרופוזל מדומה מהספק: `attestation.quote="10+ years of enterprise SaaS sales experience"`
(אמיתי, byte-exact), `demanded="2"` (משקר לגבי הערך שבציטוט עצמו), מועמד עם ~2.5 שנות
ותק (`sales.summary.tenure`).
**צפוי:** דרישת סף של 10 שנים לא אמורה להיסגר ע"י מועמד עם 2.5.
**בפועל:** `threshold_coverage` (coverage.py) משתמש ב-`demanded="2"` כפי שנשלח, ללא שום
בדיקה מול הטקסט המצוטט → `coverage="matched"`.

### A6
קלט:
```
Requirements:
- Communication skills

Benefits:
- Free lunch and snacks every day
```
פרופוזל מדומה: `attestation.quote="Free lunch and snacks every day"` (מ-section
"other"), `interpretation={source_role:"requirement", obligation:"mandatory",
composition:"single"}`.
**צפוי:** לא אמור להתקבל "requirement חובה" מציטוט מתוך פרק הטבות.
**בפועל:** `verify_interpretation` לא זורק שום exception (שני התנאים ב-שורות 61-65,
72-75 דורשים section שהוא "requirements"/"preferred" או marker בציטוט — "other" בלי
marker לא מפעיל אף אחד מהם) → עובר, נכנס ל-fit_score כ-mandatory requirement מומצא.

### A7
קלט:
```
Requirements:
- Must have 5+ years of sales experience.
- Fluent in English.
```
פרופוזל מדומה: attestation span שמתחיל בתוך הבולט הראשון ומסתיים בתוך השני (חוצה
statement boundary).
**צפוי:** ציטוט שחוצה שני statements נפרדים אמור להידחות (או לפחות לא לקבל "single"
בשקט).
**בפועל:** הלולאה ב-`verify_interpretation` (שורה 54-56) לא מוצאת אף statement שמכיל
את כל הספאן → יוצאת בלי לבדוק דבר; כל obligation/source_role שהספק הצהיר עובר.

### A8
קלט (עם "Must have" חוזר, כמו כל מודעה אמיתית):
```
Requirements:
- Must have 5+ years of B2B sales experience
- Must have native-level English
```
פרופוזל שממלא **בדיוק** את הנחיית system-v3.md:27-28: `context_quote="Must have"`.
**צפוי:** ציטוט מרקר מנדטורי אמיתי, verbatim, כפי שהפרומפט מורה לספק לספק — אמור
להתקבל.
**בפועל:** "Must have" מופיע פעמיים במקור → `_verify_context_quote_occurs`
(interpretation.py:153-156) זורק `InvalidRequirementInterpretation` → כל הפרופוזל
נדחה (`RequirementExtractionRejected`), לא רק הפריט הזה.

### A9
קלט:
```
Requirements:
- Must own the full sales cycle at a SaaS company
```
פרופוזל: `composition="any-of"`, member1.attestation.quote="full sales cycle" (מועמד:
matched, יש sales.summary.new_business), member2.attestation.quote="SaaS company".
**תיקון מהגרסה הקודמת: member2 אינו יוצא unsupported/partial דרך boundary fact.**
`_member_coverage` (ai_extraction.py:141-173) קודם קורא ל-`concept_for_quote("SaaS
company", concepts)` — ושני הפטרנים של `technology-company-sales`
(`config/requirements.json`) דורשים את המילה "sales" באותו הציטוט
(`"sales[^.;]{0,120}...compan\w*"` או ההפוך); "SaaS company" לבדו לא מכיל "sales" כלל
(SaaS ≠ sales) → **אף concept לא תואם** → `concept_for_quote` מחזיר `None` על 0
התאמות (לא על ריבוי התאמות כמו ב-A10) → `_member_coverage` מחזיר `("undetermined",
[], None)` ישירות (שורה 163-164), בלי לגעת בכלל ב-`threshold_coverage`/boundary fact.
**צפוי:** דרישה ל"מחזור מכירות מלא **בחברת SaaS**" לא אמורה להיסגר ע"י מועמד בלי ניסיון
SaaS מאומת.
**בפועל:** `member_coverages=["matched","undetermined"]`; `"matched" in member_coverages`
מספיק (ai_extraction.py:226-231) → הדרישה כולה `coverage="matched"`, האילוץ "at a SaaS
company" נעלם לגמרי — לא כי הוא נבדק ונכשל, אלא כי member1 המספיק "מכסה" עליו.

### A10
קלט:
```
Requirements:
- 5+ years of sales experience at a technology company with fluent English
```
ציטוט טבעי, שלם, כפי שהפרומפט מבקש (בולט אחד). 3 concepts תואמים בו-זמנית
(sales-closing-experience-years, technology-company-sales, english-proficiency).
**צפוי:** ציטוט חד-משמעי לבן-אדם אמור לפחות לקבל את אחד הconcepts שתואמים.
**בפועל:** `concept_for_quote` מחזיר `None` כש-`len(matches)>1` → `coverage="undetermined"`,
אפס קרדיט, ללא קשר לעובדות המועמד.

### A11
פרופוזל מדומה עם אותה requirement פעמיים (attestation/interpretation/kind/demanded
זהים) — תרחיש ריאליסטי של ספק ש"הכפיל" הצעה.
**צפוי:** כפילות אמורה להצטמצם לאובייקט אחד (כמו ב-extraction.py:132-136 בנתיב
הדטרמיניסטי), או לפחות לא להיספר פעמיים.
**בפועל:** `verify_and_cover_extraction` לא בודק ייחודיות לפני `append` → שני
`Requirement` עם אותו `requirement_id` (אותו hash קלט) ברשימה; `fit_score` סופר את
שניהם, ו-`_acceptable_requirement_ids` לא יכול להבדיל ביניהם.

### C1
קלט: תרחיש D2 (למעלה) + `AnalyzeCommand(profile_override="account-executive", ...)`
באותה בקשה.
**צפוי:** `low-confidence` שמקורו ב-extraction_score נמוך אמור להישאר פתוח גם אחרי
בחירת Profile — בחירת Profile לא "קראה" יותר מהמשרה.
**בפועל:** `unresolved_approval_reasons` (approval.py:98-101) מנקה `low-confidence`
ברגע ש-`"profile"` ב-`user_override`, כי `APPROVAL_REASONS["low-confidence"].overrides
== frozenset({"track","profile"})` (approval.py:54) — בלי קשר למקור הבעיה.

### C2
לא ניתן לבטא כטסט-על-קלט-בודד — זו טענה מבנית על שני מרחבי מחרוזות שלעולם לא נחתכים.
הטסט המתאים: `set(gap.requirement for gap in derive_gaps(lowered, track) for any lowered)`
(התוויות הקשיחות: "Salesforce", "Direct SaaS Sales preference", "Sales CRM usage",
"Strategic partnerships / channel Sales experience") מול `{concept["label"] for concept
in config["concepts"].values()}` — assert אין חיתוך, לכל טקסט אפשרי, כי אין concept
בשם salesforce/saas/crm/partnerships ב-`config/requirements.json`.
**צפוי מול בפועל:** אין הבדל בין הטקסטים — זו בדיוק הבעיה: `covered_text` (שנבנה מ-
`requirement.text`, תמיד span שחולץ) ו-`gap.requirement` (תווית קשיחה) הם שני עולמות
נפרדים שה-dedup ב-classification.py:461 מעולם לא יכול לגשר ביניהם.

---

## מה משתנה עכשיו שהחלטות #1-#3 נפתרו

(עודכן מ"מה מתייתר אם החלטה #1 היא כן" — ההחלטה כבר לא היפותטית. "החלטה #1" = שורת
דרישה שזוהתה כ-`requirement_line` אך לא מופתה לקונספט הופכת ל-
`Requirement(coverage="undetermined")` באותה רשימה ש-`fit_score` קורא. "החלטה #2" =
אין ratio threshold ל-`extraction_failed`. "החלטה #3" = `understood_elsewhere` מוסר
מסמנטיקת `extraction_failed`, נשאר קלט ל-confidence בלבד.)

**נסגרים ישירות ב-Stage 1, בלי תלות בהחלטה #1/Stage 2:**
- **D2** — נסגר לגמרי ע"י החלטה #3 לבדה (מחיקת ה-short-circuit). לא היה תלוי
  ב-denominator מלכתחילה; זה תוקן בגרסה קודמת של המסמך שרשמה אותו כ"נשאר פתוח
  כבאג לוגי" — זו הייתה טעות. אחרי Stage 1, `extraction_failed` על התרחיש של D2
  (rule-gap בודד + 0 requirements מובנים) מחזיר `True`, נכון.

**נסגרים ע"י Stage 2 (החלטה #1), בשני הנתיבים:**
- **A3** — חיווט `unmapped_statements` לרשימת ה-undetermined *הוא* התיקון, בתנאי
  המפורש שהתיקון יושב בתוך `verify_and_cover_extraction` עצמה (ר' Stage 2), לא רק
  כרשימה נלווית.
- חלק מ-**D3**'s הסימפטום (לא הבעיה כולה — ר' "נשארים פתוחים" למטה): denominator
  שכולל שורות שלא הובנו מקטין fit_score בפועל, לא רק completeness.

**מוגדרים מחדש — לא נסגרים ע"י קוד, כי הממצא המקורי היה שגוי:**
- **A4** — ר' Stage 1 ואת שורתו בטבלה. `extraction_is_failed`'s `any()` הוא ההתנהגות
  הנכונה לפי החלטה #2; אין כאן קוד לתקן. יש עדיין תלות אמיתית: A4 "עובד כמתוכנן"
  רק אחרי ש-Stage 2 נוחת **בנתיב ה-AI במפורש** — עד אז 1/20 עדיין בלתי-מיוצג שם
  (ר' Stage 2), וזה false-green בפועל, רק שהוא כפוף ל-Stage 2 ולא ל-A4 עצמו.

**נשארים פתוחים למרות זאת:**
- **D3 נשאר פתוח** — כפי שצוין, גם עם denominator מתוקן: הדוגמה `completeness≈0.56`
  שכבר מחושבת בטבלה למעלה (`(0.4+0.6·0.56)=0.736`) עדיין חוצה את `0.72/0.98≈0.735`.
  תיקון הדנומינטור מוריד completeness במקרים שהיו קודם מוסתרים לגמרי (D1-style), אבל
  אינו נוגע בבעיית כיול-הסף עצמה — ואף אחת מהחלטות #1-#3 לא קובעת מה הסף הנכון;
  זו נשארת שאלת כיול פתוחה לגמרי (לא מכוסה ע"י אף decision שנפתרה).
- **D1 נסגר ב-Stage 1** (`fit_score_from_requirements([])` מחזיר `None`) — לא תלוי
  בהחלטה #1: הדוגמה שלו (שני בוליטים בעברית שלא מקבלים אף `kind`) אף פעם לא נכנסת
  ל-`requirement_lines()` מלכתחילה, כי הבעיה שם היא בסגמנטציה, לא ב"זוהה אך לא
  מופתה". זה נשאר תיקון עצמאי ב-Stage 1 (ר' שם), רק שעכשיו יש לו תיקון קונקרטי
  ומאושר, לא רק "דורש תיקון נפרד".
- **A1's סיכון השיורי** (ר' Stage 2 למעלה) נשאר — לא תלוי בהחלטה #1, ולא נפתר ע"י
  שום החלטה שנפתרה. זהו סיכון מבני קבוע.
- **A2, A11, D4, D5, D6, A5-A10, C1, C2, D8** — כולם עצמאיים לחלוטין מהחלטות #1-#3;
  שום דבר בהם לא נסגר או משתנה על ידן.
- **D9 — עצמאי מהחלטות #1-#3, אבל עכשיו יש לו תלות חדשה נכנסת מ-Stage 2 (החלטה
  #10):** ה-`undetermined_requirement()` הסינתטי שנוצר ב-Stage 2 קובע בכוונה
  `mandatory=False` תמיד, בדיוק כדי **לא** לרשת את הבאג של D9 (`line.section`
  שגוי כש-heading בלי נקודתיים לא נסגר) לתוך קוד חדש לפני ש-Stage 6 מתקן אותו.
  המשמעות: כשD9 סוף-סוף מתוקן ב-Stage 6, יש להחליט מחדש אם `undetermined_
  requirement` צריך לעבור מ-`mandatory=False` קבוע ל-`mandatory=line.section==
  "requirements"` (עכשיו `section` יהיה אמין) — זו לא עבודה אוטומטית, זה item
  מפורש להוסיף ל-scope של Stage 6 כשמגיעים אליו.

**משנים משמעות (לא "נסגר", לא "נשאר זהה" — המדד עצמו הופך לבעל תוכן):**
- **D7** — כרגע `concept_classification_completeness` קבוע מתמטית ל-1.0 כי כל
  `ExtractedRequirement` נבנה עם concept לא-ריק. ברגע שנוצרות ישויות `Requirement`
  עם `concept=None` (מדרישות שזוהו אך לא מופתו, Stage 2), המדד **מתחיל לזוז** בפועל
  בפעם הראשונה — אבל אז צריך לבדוק מחדש אם הנוסחה שלו (`sum(item.concept)/
  len(extracted)`) עדיין אומרת משהו נכון, כי היא נכתבה כשהיה בלתי אפשרי להזיז אותה.
  ייתכן שצריך ניסוח מחדש, לא רק "הפעלה".

---

## Open product decisions

#1-#3, #7-#12 **RESOLVED**. #4-#6 remain open but do not block Stage 1 (see Stage 0).

1. **RESOLVED — YES.** שורת דרישה שזוהתה כ-`requirement_line` אך לא הצליחה להתמפות
   לקונספט הופכת ל-`Requirement(coverage="undetermined", concept=None)` שנכנס לאותה
   רשימה ש-`fit_score_from_requirements` קורא.
   **נימוק:** זו ההשלכה הישירה של docstring `fit_score_from_requirements` עצמו
   (gaps.py:53-60), שכבר מצהיר על הכוונה הזו בלי שום קוד שמייצר את ה-`Requirement`
   הזה בפועל. כל requirement כזה יעלה `total_weight` באפס קרדיט (בדיוק כמו
   `unsupported`/`undetermined` היום), יוריד את ה-fit_score בפועל, ויידלק
   `coverage-undetermined` שחוסם אישור. זה מיישם ישירות ב-Stage 2, בשני הנתיבים
   (ר' התנאי המפורש ב-Stage 2 למעלה) — ללא זה, שום דבר ב-Stage 1 לבדו לא סוגר את
   הפער שהמסמך כולו נסוב סביבו, הוא רק מעביר אותו למקום אחר (ר' "Stage 2 חייב
   לבוא מיד" ב-Stage 1).

2. **RESOLVED — אין ratio threshold ל-`extraction_failed`/`extraction_is_failed`.**
   הם נשארים בוליאניים, ומיועדים לכשל **קטסטרופלי** בלבד (0 מתוך N הובן), לא כמדד
   שלמות (לא "X% מתוך N").
   **נימוק:** partial extraction מיוצג דרך `undetermined` requirements (החלטה #1)
   ודרך `fit_score` עצמו, שיורד באופן טבעי ככל שיותר requirements הם `undetermined`.
   שני מנגנוני ענישה נפרדים על אותה תופעה — בוליאני עם סף יחס, וגם `fit_score`
   רציף — היו דורשים כיול הדדי מתמיד בלי תועלת נוספת: כל שינוי בנוסחת ה-fit היה
   מחייב לשאול מחדש אם הסף הבוליאני עדיין "מתואם", ולהפך. **השלכה ישירה:** A4
   מוגדר-מחדש (לא באג — ר' שורתו בטבלה ו-Stage 1); D1/D2 מתוקנים בלי צורך בסף
   יחס כלשהו.

3. **RESOLVED — הסרת `understood_elsewhere` מסמנטיקת `extraction_failed` לחלוטין.**
   rule-gap מקומי (salesforce/crm/saas/וכו') לא רשאי עוד לבטל כשל גלובלי.
   **נימוק:** `understood_elsewhere` נשאר קלט ל-`extraction_confidence` בלבד —
   הרצפה 0.4 ב-confidence.py:118-122, ששם המשמעות שלו נכונה ("הכללים קראו משהו, אל
   תדווח confidence אפס מוחלט"). זו טענה שונה לגמרי מ"לכן ה-extraction לא נכשל" —
   שתי הטענות התבלבלו בקוד הקיים (D2) והפרדתן היא בדיוק התיקון.

4. **Stage 7 (שערי AI) — כמה מחמיר ה-gate צריך להיות?** כל תיקון ב-A5/A6/A7/A8/A9/A10
   הוא בהכרח פשרה בין "לתפוס יותר ניסיונות זיוף" לבין "לא לדחות פלט תקין בתום-לב
   בשיעור גבוה מדי" (A8 במיוחד: אם התיקון להדיוק בבדיקת ה-uniqueness יהיה נוקשה
   מדי, נתיב ה-AI עלול להיכשל על רוב המודעות האמיתיות). דורש בדיקה אמפירית על
   מודעות אמת, לא רק ניתוח סטטי.

5. **D8 — `classification_confidence` תחת מדיניות coverage-first:** מה הציון הנכון
   לדווח כשה-coverage הוא זה שהכריע (לא ה-vocabulary)? הקוד הקיים במפורש מסמן את
   זה כשאלה פתוחה בדוקסטרינג שלו (classification.py:160-166) ולא רק כבאג שנתגלה
   כאן.

6. **C1 — `low-confidence` צריך reason-code נפרד** לפי מקור הבעיה (extraction מול
   classification), בדומה להפרדה שכבר קיימת בין `extraction-failed` ל-
   `coverage-undetermined`. מי "עונה" על כל reason חדש כזה?

7. **RESOLVED — reason חדש: `"requirements-absent"`.** `fit_score=None` שנוצר
   כתוצאה מ-`not requirements` (D1, ר' Stage 1 למעלה) חייב approval_reason משלו —
   כרגע `"extraction-failed"` נדלק אך ורק כש-`failed_extraction=True`
   (`state=="unparsed"`), ו-D1's המקרה הוא תמיד `state=="absent"`, כך שבלי reason
   חדש המשתמש מקבל `fit=UNKNOWN` בלי שום הסבר ובלי override שפותר אותו.
   **למה reason נפרד ולא הרחבת `"extraction-failed"`:** שני המצבים הם אבחנות שונות
   במכוון — `extraction_state` כבר מבחין `"absent"` (0 שורות זוהו כלל) מ-`"unparsed"`
   (שורות זוהו, 0 הובנו) בדיוק כדי לא לטשטש אותם; `extraction_failed`'s השם
   והדוקסטרינג שלה ("Requirements were stated in some form, and none of them were
   read") מדברים במפורש על המקרה השני בלבד — הרחבתה לכסות גם "לא נאמר כלום" הייתה
   מותחת את המשמעות שלה מעבר לשם ולתיעוד שלה.
   **המבנה (תואם ל-`APPROVAL_REASONS` הקיים ב-approval.py:52-76):**
   ```python
   "requirements-absent": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),
   ```
   אותו override key (`"analysis"` → `ACCEPTED_INCOMPLETE_ANALYSIS`) ואותו
   `review_code` (`ANALYSIS_INCOMPLETE`) כמו `"extraction-failed"`/
   `"coverage-undetermined"` — כי מבחינת מי שפותר את זה (המשתמש, דרך
   `apply_analysis_decisions(accept_incomplete_analysis=True)`), זו אותה החלטה:
   "המשך למרות שהניתוח לא הושלם". ה-string הנפרד נשמר כי הוא המידע היחיד שאומר
   *למה* — קריטי לדיבוג/למוצר, ותואם את הפילוסופיה הקיימת שכבר מפרידה
   `extraction-failed` מ-`coverage-undetermined` על אותו override בדיוק. **מי מדליק
   את זה:** `classify_job` ו-`rebase_requirements` (classification.py), בתנאי
   `not requirements and not failed_extraction` — ר' תוכנית הקבצים למטה.

8. **RESOLVED — רשומות היסטוריות: משאירים כפי שהן, אין migration.** `JobAnalysis`
   קיימים (כולל הרשומה המניעה את כל המסמך הזה — SuperFunnel,
   `90787e94-1401-44ba-b8e3-ef4e8aecccde`) ימשיכו להציג את ה-`fit_score`/`fit`
   הישנים (למשל `1.0`/`HIGH`) עד שמישהו מפעיל `analyze()` מחדש על אותו application.
   **שום קוד migration/re-analysis גורף לא נכתב כחלק מ-Stage 1+2.**
   **נימוק:**
   - השינוי הוא ל-*חישוב* קדימה, לא לנתונים שמורים. `JobAnalysis` כבר append-only
     עם versioning (`analysis_version`, `job_analysis_id` חדש בכל
     re-classification/correction) — המנגנון הקיים ל"הניתוח הזה כבר לא נכון" הוא
     כבר "תפעיל analyze() שוב", בלי צורך בשום דבר חדש.
   - re-analysis גורף היה עלול לשנות track/profile/emphasis/gaps/approval_reasons
     על אפליקציות שיש להן selection plans/drafts/CVs מאושרים שכבר תלויים בניתוח
     הישן — בדיוק סוג השינוי השקט ב-workflow/artifact lifecycle ש-CLAUDE.md אוסר
     ("Do not silently change workflow... application statuses, or artifact
     lifecycle"). כל re-analysis כזה, גם הכי מוצדק, הוא פעולה consequential
     שדורשת אישור מפורש per-application, לא batch job.
   - "סימון" (flag רשומות ישנות כ-stale) הוא שיפור UX לגיטימי, אבל **תכונה נפרדת**
     (שדה/פרויקציה חדשים) — לא נדרש לנכונות הנתונים של Stage 1+2 עצמו. אם רוצים
     את זה, זו משימת המשך נפרדת.
   **מה שכן נשאר פתוח:** האם להריץ `analyze()` ידנית מחדש **לרשומת SuperFunnel
   הספציפית** (לא batch) — זו החלטה נפרדת, ולא מיושמת עד אישור מפורש.

9. **RESOLVED — `rebase_requirements` מקבל `requirements_absent` כפרמטר מפורש מהקורא,
   לא מגזירה פנימית מ-`not requirements`.**
   **הבעיה שנמצאה (בדיקה מלאה של כל קוראי `rebase_requirements`):** ה-invariant
   "`requirements==[] ⟺ absent`" תקף רק כש-`requirements` נבנה טרי, **באותה קריאה**,
   מול הטקסט הנוכחי (classify_job; verify_and_cover_extraction אחרי הספליסינג).
   `rebase_requirements` עצמה **לא רואה טקסט** ולא יודעת מאיפה `requirements` הגיע —
   היא סומכת על הקורא. שני קוראים בפועל (analysis.py):
   - `prepare()` (שורה ~280, extraction AI טרי): מעביר את `verified_requirements`
     **מיד** אחרי `verify_and_cover_extraction` — טרי, ה-invariant תקף.
   - `_correct_interpretations` (שורה ~909): מעביר `corrected_requirements`
     שמקורו ב-`apply_interpretation_corrections(list(analysis.requirements), ...)`
     — **רשימה שמקורה ברשומה קיימת**, לא טרייה מול הטקסט בקריאה הזו.
   **בדקתי אם זה בפועל מסוכן:** `apply_interpretation_corrections` דורש requirement_id
   קיים לכל correction (`by_id.get(...)`, `raise UnknownRequirementForCorrection` אם
   לא נמצא) ומחזיר רשימה **באותו האורך** (רק מחליף פריטים בשם, לא מוסיף/מוריד) — ולכן
   בפועל **לא ניתן** להגיע ל-`requirements==[]` דרך הקורא הזה כשההתחלה לא הייתה ריקה,
   וגם לא ניתן להגיש correction על רשימה שכבר ריקה (אין id לתקן). כלומר: התרחיש הקונקרטי
   של "ריק שגוי מ-`_correct_interpretations`" **חסום כרגע** ע"י האילוץ הזה — אבל זו
   הגנה **עקיפה ומקרית** (תלויה בהתנהגות של פונקציה אחרת שלא נועדה להגן על זה), לא
   מכוונת, ותישבר בשקט אם `apply_interpretation_corrections` ישתנה אי-פעם (למשל
   תומך במחיקת requirement). **לכן:** דגל מפורש, לא תלות בהתנהגות עקיפה.
   **המימוש:** `rebase_requirements(..., requirements_absent: bool, extraction_failed: bool)`.
   - ב-`prepare()`: `requirements_absent = not verified_requirements` (טרי, בטוח).
   - ב-`_correct_interpretations`: `requirements_absent = "requirements-absent" in
     analysis.approval_reasons` — **בדיוק אותו תבנית שכבר קיימת בקוד** לשדה
     `extraction_failed` באותה הפונקציה עצמה (analysis.py:919,
     `extraction_failed="extraction-failed" in analysis.approval_reasons"), ועם אותו
     נימוק המתועד שם: correction משנה פרשנות של requirement אחד, לא את השאלה אם
     הפוסטינג בכלל הציג דרישות — זו תכונה של הטקסט, לא משתנה ע"י correction, ולכן
     עוברת בירושה מהניתוח הקודם ולא מחושבת מחדש.

10. **RESOLVED — `mandatory=False` לכל ישות `undetermined` סינתטית (שורה לא-ממופה).**
    **תיקון לטענה במשימה:** "undetermined ממילא coverage-undetermined חוסם" איננה
    מדויקת — `gaps_from_requirements` (gaps.py:132) מגדיר
    `hard = requirement.mandatory and requirement.coverage != "undetermined"` —
    כלומר **undetermined אף פעם לא הופך ל-hard gap, גם עם mandatory=True** (זה
    מתועד מפורשות בדוקסטרינג של הפונקציה, stage-1 plan §3.6). אז "mandatory=True
    מוסיף hard gap" שגוי כפשוטו. שני האפקטים האמיתיים של `mandatory` על ישות
    undetermined הם: (א) משקל `_MANDATORY_WEIGHT=2` במקום `_PREFERRED_WEIGHT=1`
    ב-`fit_score_from_requirements` — מכפיל את העונש שלה על fit_score; (ב) מדליק
    `coverage-undetermined` (חוסם אישור) **רק אם** לפחות ישות undetermined אחת היא
    גם mandatory (`mandatory_undetermined = any(coverage=="undetermined" and
    mandatory ...)`, classification.py:471-474/267-276).
    **למה בכל זאת mandatory=False, ולא True:** ההצעה `line.section=="requirements"`
    היא **בדיוק** אותו שדה (`StatementLine.section`) שה-D9 (עדיין לא מתוקן, Stage 6)
    הופך לשגוי — כותרת בלי נקודתיים שלא נסגרת נכון משאירה בוליטים תחת
    `section=="requirements"` גם כשהם בפועל תחת "Perks"/"Benefits". Stage 1+2
    נוחת **לפני** Stage 6 (סדר מוגדר במסמך זה), כך ש-mandatory=True על ישות סינתטית
    היה **מנציח ומגדיל** את הנזק של D9 לקוד חדש שלא היה קיים קודם: בולט הטבות
    תמים, לא-ממופה, עם section שגוי בירושה מ-D9, יקבל משקל כפול ואולי יחסום אישור —
    על תוכן שמעולם לא היה דרישה. **מה שנשמר בכל זאת כהגנה:** fit_score עצמו כבר
    מספיק — חישבתי: ברשימה שבה כל הפריטים undetermined (0 קרדיט), `mandatory`
    לא משפיע על היחס הסופי כלל (0×1=0×2=0). במקרה מעורב (1 matched + 3
    undetermined, בדיוק צורת SuperFunnel/D4), `weight=1`: `1/(1+3)=0.25`;
    `weight=2`: `1/(1+6)=0.143` — **שני הערכים כבר מתחת ל-`FIT_SCORE_MEDIUM_
    THRESHOLD=0.55`**, כלומר `fit=LOW` בשני המקרים, ללא תלות ב-mandatory. ואומתתי
    (grep) שכשל `fit=="low"` הוא gate **עצמאי ונפרד** מ-`coverage-undetermined`:
    חוסם draft generation (`drafts/generation.py:138`) וvalidation
    (`validation.py:292`) דרך `LOW_FIT_REQUIRES_ACCEPTANCE`, עד decision מפורש
    `accepted-low-fit` — כך שהתרחיש שה-mandatory=True נועד להגן עליו (משרה עם
    דרישות שלא נקראו) כבר חסום ע"י ה-fit-gate בלי תלות בבחירת mandatory כאן.
    **מסקנה:** mandatory=False עכשיו, כיוון שמרני שלא מגדיל blast radius של D9
    שלא-תוקן, בלי לאבד הגנה בפועל. לשקול מחדש ל-mandatory מ-section אחרי ש-D9
    מתוקן (Stage 6) — ר' "מה מתייתר" בהמשך, יש להוסיף שם רישום.

    **תוספת — השלכה שנבדקה במפורש: `coverage-undetermined` לעולם לא נדלק מישויות
    סינתטיות.** `mandatory_undetermined = any(coverage=="undetermined" and
    mandatory ...)` — כש-`mandatory=False` קבוע לכל ישות סינתטית, הביטוי הזה
    לעולם לא True **רק** בגללן (הוא עדיין יכול לדלוק מישות undetermined *אמיתית*,
    למשל threshold עם scale לא-פרסבל, ששם `mandatory` הוא ערך מאומת אמיתי, לא
    ברירת מחדל). **המשמעות בפועל:** משרה שכל שורות הדרישה שלה לא מופו כלל
    (כל ה-`requirements` הן ישויות סינתטיות) תקבל `fit_score=0.0`/`fit=LOW`, אבל
    **בלי** `coverage-undetermined` — החוסם היחיד שנשאר הוא
    `LOW_FIT_REQUIRES_ACCEPTANCE`, שנפתר ב-`accepted-low-fit`.

    **זה לא מקובל כפי שהוא, והכרעתי לתקן:** `accepted-low-fit` ו-
    `accept_incomplete_analysis` הם שתי טענות שונות מהותית — "הבנתי את הדרישות,
    והמועמד לא מתאים אליהן טוב" מול "המנוע לא הצליח לקרוא את הדרישות בכלל". משרה
    שכולה לא-ממופה **אינה** "מועמד עם fit נמוך" — ה-fit_score=0.0 שמחושב לה הוא
    תוצר לוואי חשבוני (0 קרדיט × כל משקל = 0), לא הערכה אמיתית של המועמד, בדיוק
    אותה אבחנה בין "לא מתאים" ל"לא ידוע" שכל המסמך הזה בנוי סביבה (gaps.py's own
    docstring: "we could not tell is not you lack this"). לתת ל-`accepted-low-fit`
    "לענות" על זה מציג למשתמש מסר שגוי ("המועמד נכשל בבדיקה") כשה-אמת היא "לא
    בדקנו כלום". **הפתרון: reason חדש, `"requirements-unmapped"`** — ר' החלטה #12
    למטה — נדלק כש-**קיימת** ולו ישות סינתטית אחת (`unmatched_requirement_lines`
    לא ריקה), **ללא תלות ב-mandatory וב-section**: לא רק בגלל ש-mandatory=False
    קבוע (אין שם מידע לבדוק), אלא **בכוונה**, כדי לא לצטרך לסמוך על `.section`
    בכלל כאן — עקבי עם הנימוק שכבר הוביל ל-mandatory=False (לא לגעת ב-D9 בכלל,
    בשום כיוון, עד Stage 6). המחיר: גם בולט "Nice to have" שלא מופה ידליק את זה
    (over-blocking קל, לא under-blocking) — כיוון שמרני, לא מסוכן, עקבי עם רוח
    כל שאר ההחלטות כאן.

11. **RESOLVED — ordinal לישויות undetermined: discriminant נפרד ב-extraction_version
    (כמו `RULE_INTERPRETATION`), לא שיתוף `seen` עם `extract_requirements`.**
    **הבעיה שנבדקה:** `extract_requirements`'s `seen: dict[str,int]` (extraction.py:108)
    מפתחו הוא `normalize_span(matched)` — **תת-המחרוזת שהרג'קס תפס**, לא כל
    ה-statement. שורה לא-ממופה שלמה (הטקסט **המלא** של הבולט) יכולה, במקרה גבולי,
    להיות שווה (מנורמל) לתת-מחרוזת שנתפסה במקום אחר בפוסטינג (למשל בולט כפול
    שחוזר מילה-במילה על מה שנתפס בתוך משפט ארוך יותר במקום אחר) — ואז שני האובייקטים
    (extracted ו-undetermined) עם אותו `identity_span`, אותו `extraction_version`,
    ואותו `ordinal` (שניהם 0, אם כל אחד סופר בנפרד) יתנגשו על אותו `requirement_id`.
    **זה אפשרי בפועל**, גם אם נדיר — אין שום דבר שמונע במפורש טקסט חוזר על עצמו.
    **הפתרון (לא שיתוף `seen` — זה היה דורש לשנות את חתימת/ה-return type של
    `extract_requirements`, פונקציה קיימת עם קוראים אחרים):** קבוע חדש
    `UNDETERMINED_INTERPRETATION` (ב-extraction.py, לצד `RULE_INTERPRETATION`),
    מצורף ל-`extraction_version` בדיוק כמו ש-`_identified()` (classification.py:139-141)
    כבר עושה לrule-derived gaps: `extraction_version=f"{extraction_version}:
    {UNDETERMINED_INTERPRETATION}"`. זה מבטיח **קונסטרוקטיבית** אפס התנגשות מול
    extracted items (extraction_version שונה) ומול rule-derived gaps
    (discriminant שונה מ-`RULE_INTERPRETATION`) — לא תלוי בזיהוי כל התרחישים
    מראש, בדיוק הנימוק המתועד כבר ב-`_identified()`'s docstring (classification.py:
    129-134, "A silent, unmarked version here would let a rule-derived gap and an
    AI-extracted requirement... collide"). **ordinal בתוך האצווה שלי:** לא צריך
    `seen` dict בכלל — `_identified()` עצמה (classification.py:149) פשוט משתמשת
    ב-`enumerate(gaps)` הפוזיציוני, בלי לבדוק כפילויות טקסט; אני מאמץ אותו תקדים:
    `for ordinal, line in enumerate(unmatched_lines)`. יציב בין הרצות חוזרות על
    אותו טקסט כי `_segments`/`requirement_lines` מסדרים תמיד לפי סדר ה-offset
    בטקסט (דטרמיניסטי), ומספיק לייחודיות כי ה-hash תלוי גם ב-`ordinal` — אפילו
    שתי שורות עם טקסט מנורמל זהה יקבלו ordinal שונה (מיקום שונה) ולכן id שונה.

    **תיעוד השלכה — הזזת requirement_id ברגע ששורה הופכת ממופה (מכוון, לא באג
    עתידי):** ה-discriminant בעצמו גורם לכך שברגע ש-`config/requirements.json`
    מתרחב (Stage 6 או כל שינוי אחר) כך ששורה שהייתה unmapped הופכת עכשיו למופה
    לconcept אמיתי, ה-`requirement_id` שלה **משתנה**: קודם נבנה עם הdiscriminant
    `UNDETERMINED_INTERPRETATION` דרך `undetermined_requirement()`, עכשיו נבנה בלי
    שום discriminant (או עם discriminant אחר, אם AI) דרך `extract_requirements`/
    `cover_ai_requirement` הרגילים. זו **בדיוק** אותה תופעה ש-`RULE_INTERPRETATION`
    כבר מייצר במכוון היום (`_identified()`'s docstring, classification.py:129-134)
    וש-`correct_interpretation`'s docstring (ai_extraction.py:349-355) כבר מתעד
    כעיקרון כללי: "The requirement id moves... This is what makes a prior gap
    acceptance not silently apply to the corrected requirement's meaning... and a
    moved id is exactly such a refusal." **בדקתי אם יש נזק מעשי:** ישות
    `undetermined` **לעולם לא זכאית ל-hard gap** (gaps.py:132,
    `coverage != "undetermined"` נדרש) — ולכן **לא ניתן מלכתחילה** לרשום עליה
    `accepted_requirement_ids` (`_acceptable_requirement_ids` דורש
    `gap.severity=="hard"`, מסרב אחרת) — כך שאין "acceptance שנרשם על undetermined"
    שיכול להיפגע מהזזת ה-id, כי הוא מעולם לא היה יכול להירשם. הווקטור היחיד
    שכן יכול להתייחס ל-id של ישות סינתטית הוא `apply_interpretation_corrections`
    (מתקן פרשנות של requirement קיים כלשהו, גם לא-hard) — אבל תיקון כזה בונה id
    חדש משלו דרך `correct_interpretation` (מבוסס על `requirement.extractor`,
    לא על ה-discriminant של השורה המקורית), כך שהוא כבר עצמאי מ-id העתידי
    שהקלסיפיקציה "הטבעית" הייתה מייצרת בכל מקרה — אין כאן התנגשות נוספת.
    **פריט המשך קטן שנחשף תוך הבדיקה, לא לפעולה עכשיו:** `undetermined_requirement()`
    לא קובעת שדה `.extractor` (בניגוד לישויות ה-AI, שמקבלות `extractor=` מפורש
    ב-`verify_and_cover_extraction`) — כדאי להשוות זאת בזמן המימוש כדי ש-
    `correct_interpretation`'s `requirement.extractor or "corrected"` יתנהג עקבי
    גם על ישות סינתטית מתוקנת.

    **תיקון קטן שנמצא תוך הבדיקה (component_id collision):** התוכנית המקורית
    השתמשה ב-`MissingComponent(component_id="unmapped", ...)` לישות הסינתטית —
    אך `"unmapped"` **כבר בשימוש** ב-`cover_ai_requirement`'s ענף
    `concept_for_quote is None` (ai_extraction.py:258-260), למקרה שונה לגמרי
    (ציטוט AI שכן קיים אך לא זוהה concept). משנה ל-`component_id="unmapped-
    statement"` לישות הסינתטית, כדי שלא יתבלבלו אם משהו אי-פעם יבדוק שדה זה.

12. **RESOLVED — reason חדש: `"requirements-unmapped"`.** נובע ישירות מהתוספת
    להחלטה #10 למעלה: כש-`unmatched_requirement_lines(...)` לא ריקה (קיימת ולו
    ישות `undetermined` סינתטית אחת), מודלק reason נפרד — **לא** נשען על
    `coverage-undetermined` (שנשאר גדור ל-mandatory=True אמיתי בלבד, ללא שינוי),
    ו**לא** נגזר מ-`.mandatory`/`.section` על התוצאה (שני השדות לא-אמינים כאן
    בכוונה, ר' #10). **מבנה זהה לתבנית הקיימת** (approval.py:52-76):
    ```python
    "requirements-unmapped": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),
    ```
    אותו override (`accept_incomplete_analysis`) ואותו review_code כמו
    `"extraction-failed"`/`"coverage-undetermined"`/`"requirements-absent"` — כולן
    "המנוע לא סיים לקרוא, אשר במפורש כדי להמשיך", לא תלונה על המועמד. **מי מדליק
    את זה, ואיפה נדרש פרמטר מפורש (אותו מבנה כמו #9):** ב-`classify_job`, מחושב
    inline מ-`bool(unmatched_lines)` (רשימה טרייה, נבנתה באותה קריאה). ב-
    `rebase_requirements` — **פרמטר מפורש נוסף**, `requirements_unmapped: bool`,
    לאותה סיבה בדיוק שהובילה ל-#9 (הפונקציה לא רואה טקסט, לא יכולה לדעת אם
    `requirements` שהיא קיבלה כבר עבר splice בקריאה הזו): ב-`prepare()` מחושב
    `bool(unmatched_lines)` טרי; ב-`_correct_interpretations` יורש מ-
    `"requirements-unmapped" in analysis.approval_reasons` — אותו תבנית ירושה
    בדיוק כמו `extraction_failed`/`requirements_absent`.

    **מה נחת בפועל (נוסף אחרי היישום; שתי נקודות שלא היו כתובות כאן מראש):**
    - **הגארד `and not requirements_absent`.** התנאי בפועל ב-`classify_job` הוא
      `bool(unmatched_lines) and not requirements_absent`. הוא הגנתי בלבד: אם
      `requirements` ריקה אז `requirement_lines` ריקה ולכן `unmatched_lines`
      ריקה גם היא, כך ששני ה-reasons לא יכולים להידלק יחד. הוא כתוב כדי שאם
      ה-invariant הזה יישבר אי-פעם, תידלק אבחנה אחת ולא שתיים סותרות.
    - **`requirements-unmapped` יכול להידלק יחד עם `extraction-failed`, וזה נכון.**
      מודעה שבה זוהו שורות דרישה ואף אחת לא הובנה היא גם `state=="unparsed"`
      (⇒ `extraction-failed`) וגם בעלת שורות לא-ממופות (⇒ `requirements-unmapped`).
      שתי האבחנות נכונות בו-זמנית ואומרות דברים שונים: הראשונה "אפס מתוך N",
      השנייה "הנה אילו שורות". אותו override עונה על שתיהן, כך שזה לא מוסיף
      צעד למשתמש. `AMBIGUOUS_HEBREW_JOB` הוא בדיוק המקרה הזה
      (`tests/test_classification_policy.py`).

    **שלוש האבחנות זו מול זו, לסיכום:**

    | reason | נדלק כש- | אומר |
    | --- | --- | --- |
    | `requirements-absent` | `requirement_lines(text) == []` | המודעה לא הציגה שום דבר שנקרא כדרישה |
    | `requirements-unmapped` | `unmatched_requirement_lines(...)` לא ריקה | הוצגו דרישות, לפחות אחת לא מופתה לאף concept |
    | `coverage-undetermined` | קיימת ישות `undetermined` שגם `mandatory=True` | דרישה **מאומתת** כחובה שלא ניתן היה להכריע את הכיסוי שלה |

    השלישית **לעולם לא נדלקת מישות סינתטית** (`mandatory=False` קבוע, החלטה #10) —
    זה בדיוק הפער ש-`requirements-unmapped` נועד לסגור. שלושתן נענות ע"י
    `apply_analysis_decisions(accept_incomplete_analysis=True)` ורק על ידו.

---

## Stage 1+2 — implementation file plan

**Planning only — no code has been edited yet.** Order below is edit order (each step
compiles/imports cleanly on top of the previous one).

### 1. `cv_engine/domain/analysis/requirements/extraction.py` — shared helpers (new code, no behavior change to existing functions) — justified by decisions **#1** (the helpers exist to implement it), **#10** (`mandatory=False`), **#11** (discriminant + ordinal)

Two new functions, placed beside `requirement_id`/`normalize_span`/`ExtractedRequirement`
because both call sites (deterministic classification.py, AI ai_extraction.py) already
import from this module — no new cross-module dependency:

- `unmatched_requirement_lines(text, concepts, mapped_spans) -> list[StatementLine]` —
  `requirement_lines(text, concepts)` filtered to lines no span in `mapped_spans`
  overlaps. `mapped_spans` is `[(item.start, item.end) for item in extracted]` in the
  deterministic path, `mapped_spans` (already built) in the AI path — same overlap
  predicate already used by `_understood`/`unmapped_statement_ids`/
  `extraction_is_failed`, reused verbatim rather than reinvented.
- `undetermined_requirement(line: StatementLine, *, normalized_hash, extraction_version, ordinal) -> Requirement` —
  builds one `Requirement(coverage="undetermined", concept=None, kind="presence",
  mandatory=False, missing_components=[MissingComponent(component_id=
  "unmapped-statement", label="No recognised concept")])` — `"unmapped-statement"`,
  **not** `"unmapped"` (that string is already used by `cover_ai_requirement`'s own
  `concept_for_quote is None` branch, ai_extraction.py:258-260, for a different case —
  collision noted and fixed under decision #11's addendum). **`mandatory=False`
  always — decision #10, see its full reasoning and the D9 cross-link there:**
  reusing `line.section=="requirements"` here would inherit D9's not-yet-fixed
  section-inheritance bug (Stage 6, lands after Stage 1+2) into new code; `fit_score`
  alone (verified: 0.25/0.143 either way in the mixed-case arithmetic, both under
  `FIT_SCORE_MEDIUM_THRESHOLD`) plus the independent, already-existing
  `LOW_FIT_REQUIRES_ACCEPTANCE` gate (`drafts/generation.py:138`,
  `validation.py:292`) already block the scenario this would have protected —
  revisit once D9 ships.

**`requirement_id`/`ordinal` source (your specific question, refined per decisions
#11):** the *existing* `requirement_id()` function (extraction.py:199-239), called
with **no** `interpretation`/`kind`/`demanded` (same shape the deterministic path's
own extracted items use — a synthesized entry never had an interpretation
proposed/verified for it). Inputs: `normalized_hash` (the snapshot's, as everywhere
else); `extraction_version` = base value (`concepts.extraction_version` deterministic /
the AI path's own `extractor` string) **with a new discriminant constant appended** —
`UNDETERMINED_INTERPRETATION` (new, beside `RULE_INTERPRETATION`) — exactly
`_identified()`'s own pattern (classification.py:139-141) for the identical
collision class its docstring already names (classification.py:129-134). Without
this, an unmatched line's full-statement `identity_span` could coincide with some
*other* extracted item's matched-substring `identity_span` elsewhere in the same
posting, colliding on one `requirement_id`. `ordinal` = plain `enumerate()` position
over the unmatched-lines list — no duplicate-text `seen` dict needed (mirrors
`_identified()`'s own `enumerate(gaps)` at classification.py:149, not
`extract_requirements`'s `seen` scheme) — stable because `_segments`/
`requirement_lines` always order by text offset, and sufficient because the hash
already includes `ordinal`, so two lines with identical normalized text still get
distinct ids from their distinct positions.

Imports to add: `from .segmentation import requirement_lines, StatementLine` (currently
only imports `_segments`); `Requirement, MissingComponent` added to the existing
`from ...contracts.analysis import (...)` line; new module-level constant
`UNDETERMINED_INTERPRETATION = "undetermined-interpretation-v1"` beside
`RULE_INTERPRETATION`.

### 2. `cv_engine/domain/analysis/requirements/confidence.py` — justified by decision **#3** only

Remove `understood_elsewhere` from `extraction_failed()`'s signature and body
(confidence.py:74-96) — delete the `if understood_elsewhere: return False` short-circuit
and the parameter entirely. `extraction_confidence()` (confidence.py:99-123) is
**untouched** — `understood_elsewhere` stays there, unchanged, as the sole legitimate
consumer (the 0.4 floor).

### 3. `gaps.py` — **NO CHANGE, DELIBERATE — do not "fix" this.** Justified by
decision **#9**: the `None`-override for an empty/absent `requirements` list lives
entirely at the call sites (`classify_job`/`rebase_requirements`'s own
`requirements_absent`/`requirements_unmapped` parameters, steps 5-6 below), never
inside `fit_score_from_requirements` itself. Its docstring and its `1.0`-on-empty
behavior are **correct as written** and stay untouched — a reader who thinks "D1's
fix must go here" is wrong; re-read decision #9 before touching this file.

### 4. `cv_engine/domain/analysis/approval.py` — justified by decisions **#7** and **#12** (two new entries, not one)

Add **two** entries to `APPROVAL_REASONS` (approval.py:52-76):
```python
"requirements-absent": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE),   # decision #7
"requirements-unmapped": ApprovalReason(frozenset({"analysis"}), ANALYSIS_INCOMPLETE), # decision #12
```
with a comment distinguishing both from `"extraction-failed"`/`"coverage-undetermined"`
and from each other (text drafted in decisions #7/#12 above — `-absent` means zero
requirement-bearing text was found at all; `-unmapped` means some was found but at
least one statement couldn't be classified to a concept). Check for a "derived guard"
test enforcing every emitted reason string appears in this table (approval.py's own
comment references one — "the guard that derives this table's key set from the code
that emits reasons"); locate it during implementation (likely `tests/test_analysis.py`
or `test_classification_policy.py`) so a missed registration fails loudly rather than
silently, per this repo's own stated guard philosophy.

### 5. `cv_engine/domain/analysis/classification.py` — the two orchestration points — justified by decisions **#1** (splice), **#2/#3** (`failed_extraction` call shape), **#7/#9** (`requirements_absent`), **#10/#12** (`requirements_unmapped`)

**`classify_job`** (classification.py:308-517) — `requirements`/`unmatched_lines` are
built fresh here, so both booleans below are computed inline, safely (no
explicit-param concern; that's specific to `rebase_requirements`, below):
- After `requirements = cover_requirements(extracted, facts=facts, concepts=concepts)`
  (~line 333): compute `mapped_spans = [(item.start, item.end) for item in extracted]`,
  `unmatched_lines = unmatched_requirement_lines(text, concepts, mapped_spans)`
  (decision #1), then splice `undetermined_requirement(...)` for each line in
  `unmatched_lines` onto `requirements`, **before**
  `requirement_profile_scores`/`gaps_from_requirements` run (both already handle an
  `undetermined`, no-supporting-facts `Requirement` correctly — zero Profile-score
  contribution, warning-not-hard gap by construction regardless of `mandatory` per
  decision #10 — no changes needed there).
- `failed_extraction = extraction_failed(text, extracted, concepts)` — drop the
  `understood_elsewhere=bool(rule_gaps)` kwarg (function no longer accepts it, per
  decision **#3**). `rule_gaps`/`bool(rule_gaps)` is **still** passed to
  `extraction_confidence(..., understood_elsewhere=bool(rule_gaps))` — unchanged call.
- `requirements_absent = not requirements and not failed_extraction` (decision **#7**;
  mutually exclusive by the Stage-2 invariant *for this function specifically*, since
  `requirements` is always freshly built here — the `and not failed_extraction` guard
  is defensive, not load-bearing).
- `requirements_unmapped = bool(unmatched_lines) and not requirements_absent`
  (decision **#12**; the `and not requirements_absent` guard is defensive — if
  `requirements` is empty, `unmatched_lines` is necessarily empty too, so this never
  actually fires alongside `requirements_absent` in practice).
- `fit_score = None if (failed_extraction or requirements_absent) else
  fit_score_from_requirements(requirements)` — **`gaps.py` itself is not touched, see
  step 3; do not add a `None`-branch there.**
- `reasons` list: add `*(["requirements-absent"] if requirements_absent else [])` and
  `*(["requirements-unmapped"] if requirements_unmapped else [])`, alongside the
  existing `extraction-failed`/`coverage-undetermined` entries.
- **Update the stale comment** at classification.py:466-470 ("The deterministic
  `cover_requirements` never itself emits `undetermined` today") — false after this
  change; `cover_requirements` still doesn't, but `classify_job` now splices
  `undetermined` entries in right after calling it.

**`rebase_requirements`** (classification.py:221-305, AI path) — **signature change,
decision #9 (and #12 for the second parameter):** add two explicit boolean parameters
— `requirements_absent: bool` and `requirements_unmapped: bool` — alongside the
existing `extraction_failed: bool`. **Not** derived internally from `not
requirements`/inspecting `requirements` for unmapped entries, because this function
doesn't know whether its `requirements` argument was freshly spliced against the
current text or passed through from an existing record (see decision #9's full
reasoning — the same argument applies identically to `requirements_unmapped`). Body:
same `fit_score` ternary and both new reason additions as `classify_job`, but reading
the *parameters* directly instead of computing them.

### 6. `cv_engine/application/services/analysis.py` — both `rebase_requirements` call sites (new file in the plan, per decisions **#9** and **#12**)

- `prepare()` (~line 280, fresh AI extraction): after `verify_and_cover_extraction`
  returns `requirements`/`unmatched_lines` (step 7 below, already spliced), pass
  `requirements_absent=not verified_requirements,
  requirements_unmapped=bool(unmatched_lines) and bool(verified_requirements)` into
  `rebase_requirements` — safe here because both were just computed against
  `job_text` in this same call. (`verify_and_cover_extraction`'s return signature may
  need to also surface `unmatched_lines`/its boolean, not just the spliced
  `requirements` list, for this caller to compute `requirements_unmapped` without
  re-deriving it — confirm exact return shape when implementing step 7.)
- `_correct_interpretations()` (~line 909): pass
  `requirements_absent="requirements-absent" in analysis.approval_reasons,
  requirements_unmapped="requirements-unmapped" in analysis.approval_reasons` —
  **both** inherited from the analysis being corrected, mirroring the existing,
  already-documented pattern one line above it for `extraction_failed=
  ("extraction-failed" in analysis.approval_reasons)` (analysis.py:919's own comment
  explains the identical reasoning, decision #9: a correction changes one
  requirement's interpretation, not whether the posting stated/mapped requirements at
  all — carried forward, not re-derived, for all three signals alike).

### 7. `cv_engine/domain/analysis/requirements/ai_extraction.py` — the AI-path splice — justified by decisions **#1** (splice itself) and **#11** (discriminant)

In `verify_and_cover_extraction` (ai_extraction.py:466-564): it already computes
`mapped_spans` (per-requirement, built through the loop) and, near the end, `lines =
requirement_lines(source_text, concepts)` for the `by_ai` count. Reuse both: call
`unmatched_lines = unmatched_requirement_lines(source_text, concepts, mapped_spans)`
and splice `undetermined_requirement(...)` for each onto the `requirements` list this
function returns — same helper as step 1, `extraction_version` = the AI-verified
items' own `extractor` string **with `UNDETERMINED_INTERPRETATION` appended**
(decision #11 — not the bare `extractor` string, to avoid colliding with the
AI-verified items themselves). Consider surfacing `unmatched_lines` (or just
`bool(unmatched_lines)`) in this function's return value too, since step 6's
`prepare()` caller needs it to compute `requirements_unmapped` (decision #12) without
recomputing `unmatched_requirement_lines` a second time from scratch.

`extraction_is_failed` (ai_extraction.py:567-593) — **no change.** It never had a
rule-gap escape hatch (that was D2's deterministic-only bug); its own `absent`→`False`
case is handled uniformly by step 5/6's explicit `requirements_absent`/
`requirements_unmapped` parameters in `rebase_requirements`, not by touching this
function.

### 8. Tests — **written; see "מה נחת" below the list**

- `tests/test_analysis.py` — likely asserts `fit_score==1.0`/`fit=="high"` for
  currently-empty-requirements inputs; these need updating to the new expected values.
  Also probably home to the `APPROVAL_REASONS` derived-guard test (step 4).
- `tests/test_classification_policy.py` — `classify_job` reasons-table coverage; add a
  `requirements-absent` case and a separate `requirements-unmapped` case (decisions
  #7/#12 — distinct triggers, both need their own coverage).
- `tests/test_ai_tasks.py` — `verify_and_cover_extraction`/`understanding.by_ai`
  coverage; add an unmatched-line → `undetermined` case, matching
  `tests/test_ai_tasks.py:1048`'s existing `by_ai==0` assertion style (already read
  during verification — same file already exercises this shape).

**מה נחת בפועל בטסטים:**

- `tests/test_analysis.py` — נוספו: שני ה-helpers ברמת היחידה, אי-התנגשות
  `requirement_id` מול הדיסקרימיננט ואורדינל פוזיציוני (#11), הספלייס והניקוד,
  אי-הפיכה ל-hard gap ואי-הדלקת `coverage-undetermined` (#10), ושני כיווני
  הפרמטרים המפורשים של `rebase_requirements` (#9/#12). עודכנו עשרה טסטים
  שקיבעו בדיוק את ההתנהגות שהוחלפה (`requirements == []`, `fit == HIGH` על
  רשימה ריקה, `understood_elsewhere=True`, חתימת `rebase_requirements`, ורשימת
  ה-reasons של `AMBIGUOUS_HEBREW_JOB`).
- `tests/test_classification_policy.py` — מקרה `requirements-absent` ומקרה
  `requirements-unmapped` בנפרד, ובדיקה ששתיהן נענות רק ע"י
  `accept_incomplete_analysis`.
- `tests/test_ai_tasks.py` — ספלייס נתיב ה-AI דרך ה-Operation runner האמיתי,
  כולל ש-`by_ai` לא מקבל קרדיט על ישות סינתטית.
- **הגארד הנגזר הקיים** (`test_every_approval_reason_the_engine_records_is_registered`,
  `tests/test_analysis.py`) קולט את שני ה-reasons החדשים מ-AST של
  `classification.py` — לא נדרשה בו שום רשימה ידנית, וזה בדיוק הנוהל.
- **תשעה טסטים ב-`tests/test_ai_tasks.py` שנשענו על `ACCOUNT_MANAGER_JOB`**
  (מודעה ללא שורת דרישה) נחסמו ב-generation ע"י `requirements-absent`. הם
  בודקים drafting/regeneration ולא analysis — ה-assertions שלהם הן על
  `edit_version`/`content_hash`/`failure_code`/lifecycle, אף אחת לא על
  `JobAnalysis`. הפתרון: הם עוברים את שער הניתוח דרך
  `apply_analysis_decisions(accept_incomplete_analysis=True)` (helper
  `_accepting_incomplete_analysis`), כלומר אותו מסלול בדיוק שמשתמש אמיתי עובר.
  **`ACCOUNT_MANAGER_JOB` עצמו לא שונה** — שינוי הפיקסצ'ר היה מסתיר שהשער
  עובד, ומשנה קלט משותף מחוץ לגבולות תוכנית הקבצים.
