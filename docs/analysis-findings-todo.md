# Analysis/Classification Findings — Verification & Fix-Order TODO

Source: external review (Claude web) of the requirement extraction / classification /
fit-scoring pipeline, triggered by a real production record (`SuperFunnel` /
Account Executive, application `90787e94-1401-44ba-b8e3-ef4e8aecccde`) where
`fit_score=1.0` was computed from a single extracted requirement while
`confidence=0.429`. Every finding below was re-verified directly against the code in
this session (file:line cited), independent of the external review's own citations.

**Planning only. No code changed. No tests run.**

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
catch this, `extraction_failed`, is itself gameable in four independent ways (D1, D2, A4,
and the `understood_elsewhere` short-circuit inside D2) and is never even computed for
the AI path's own confidence (A2).

Everything below is a specific way this general shape manifests.

## Fix order

Findings are grouped into stages. A stage should land, and its own focused tests pass,
before the next stage is attempted — per this repo's stage-gate rule (one stage per
session/PR, full gate at the boundary). Within a stage, order is not significant.

### Stage 0 — Product decision required before any of this is coded

See **Open product decisions** at the end. Stage 1 cannot be written correctly without
an answer to decision #1.

### Stage 1 — Root: failure detection is too permissive (both paths)

`D1`, `D2`, `A4` — these three decide *whether an analysis is trustworthy at all*. Fix
them together: they all touch `extraction_failed` / `extraction_is_failed`, and a
narrow fix to one without the others just moves the false-green to a neighboring case.

### Stage 2 — Denominator unification (depends on Stage 0 decision + Stage 1)

`D3`, `A1`, `A3` — once Stage 0/1 land, these are largely the *same* change: unmatched
requirement-bearing text (deterministic) and `unmapped_statements` (AI) both need to
enter the same list `fit_score` reads, at zero credit.

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
| **D1** | קריטי — ירוק מלא, 0 approval reasons | [confidence.py:42-45,66-68,96](../cv_engine/domain/analysis/requirements/confidence.py#L42-L96), [gaps.py:62-63](../cv_engine/domain/analysis/gaps.py#L62-L63) | `requirement_lines(text)==[]` → `extraction_completeness` returns `None` → state `"absent"` (not `"unparsed"`) → `extraction_failed` returns `False` (only checks `state=="unparsed"`) → `fit_score_from_requirements([])==1.0` | שורש; מוזג עם D2/A4 בשלב 1 | **CONFIRMED** — קראתי כל שרשרת הקריאות; ההתנהגות תואמת בדיוק את התיאור, כולל ההודאה בדוקסטרינג של gaps.py:53-60 שהמנגנון סומך על `extraction_failed` להבחין בין "אין דרישות בכלל" ל"דרישות שלא זוהו". ההבחנה הזו לא קיימת בפועל: `extraction_failed` (confidence.py:96) בודק אך ורק `state=="unparsed"`; `state=="absent"` (0 שורות זוהו) עובר תמיד כ-`False`, בלי שום דרך להבדיל "משרה שבאמת לא מציבה דרישות" מ"משרה שהסגמנטר פשוט לא זיהה בה אף שורת דרישה". |
| **D2** | גבוה — extraction_failed מנוטרל ע"י gap-כלל יחיד | [classification.py:441-444](../cv_engine/domain/analysis/classification.py#L441-L444), [confidence.py:94-95](../cv_engine/domain/analysis/requirements/confidence.py#L94-L95), [gaps.py:262-270](../cv_engine/domain/analysis/gaps.py#L262-L270) | `understood_elsewhere=bool(rule_gaps)` → `if understood_elsewhere: return False` **לפני** even בדיקת ה-state — כלומר גם `state=="unparsed"` (שורות זוהו, 0 הובנו, לא רק "absent") מנוטרל | שורש; שלב 1 | **CONFIRMED, והיקף רחב מהמתואר**: קראתי `confidence.py:94-96` — ה-short-circuit קורה *לפני* חישוב ה-state בכלל, כך שהבאג לא מוגבל למקרה "0 requirements" (כפי שהדוגמה המקורית תיארה) אלא לכל מקרה שבו נמצא ולו gap-כלל אחד (salesforce/crm/saas/partnership/years-threshold) — גם אם 20 שורות דרישה זוהו ואף אחת לא הובנה. |
| **D3** | גבוה — סף האישור עובר בקריאה חלקית | [approval.py:14](../cv_engine/domain/analysis/approval.py#L14), [confidence.py:99-123](../cv_engine/domain/analysis/requirements/confidence.py#L99-L123), [classification.py:153-168,450-454](../cv_engine/domain/analysis/classification.py#L153-L168) | עם `classified=1.0` (ר' D7) והנוסחה `(0.4+0.6·completeness)·classified`, מספיק `completeness≈0.56` כדי לחצות `0.72/0.98≈0.735` | תלוי בהחלטת מדיניות #1 (Stage 0) + Stage 1/2 | **CONFIRMED** — שחזרתי את החשבון ישירות מהנוסחאות; מספרי הדוגמה (0.735, c≥0.558) עקביים עם קריאת הקוד, בהנחת `classification_confidence` גבוה טיפוסי. |
| **D4** | בינוני-גבוה — בולט עם 3 בקשות נספר כיחידת "הבנה" אחת | [confidence.py:14-25](../cv_engine/domain/analysis/requirements/confidence.py#L14-L25), [extraction.py:118-167](../cv_engine/domain/analysis/requirements/extraction.py#L118-L167), [segmentation.py:241](../cv_engine/domain/analysis/requirements/segmentation.py#L241) | `_understood` בודק חפיפת offset בין ה-`StatementLine` המלא (כל המשפט) לבין ה-`ExtractedRequirement.span` שהוא רק תת-מחרוזת שהרג'קס תפס — משפט אחד ארוך עם 3 דרישות, רק 1 חולצה, נספר כ"מובן" במלואו | עצמאי | **CONFIRMED** — `item.start`/`item.end` הם offsets של ה-regex match בלבד (extraction.py:141-165), לא של המשפט; `_understood` (confidence.py:21-25) סופר overlap ברמת ה-line, לא ברמת המושג. `segmentation.py:241` מוסיף אפקט נלווה: שורה שממשיכה משפט קודם (lowercase, ללא bullet) ממוזגת לאותה יחידה. |
| **D5** | גבוה — dedup קובע mandatory/preferred לפי המופע הראשון | [extraction.py:132-147](../cv_engine/domain/analysis/requirements/extraction.py#L132-L147), [requirements.json:43-68](../config/requirements.json#L43-L68) | דה-דופ (שורה 132-136, `concept`+`demanded`) רץ **לפני** חישוב mandatory/preferred (שורה 147) → אזכור ראשון תחת "About us" (preferred) "בולע" את המופע השני תחת "Requirements:" (mandatory) | עצמאי | **CONFIRMED, עם תנאי מוקדם שאומת**: cue-word matching ב-`_statement_kind` ([segmentation.py:169-171](../cv_engine/domain/analysis/requirements/segmentation.py#L169-L171)) הוא **ללא תלות בסקשן** — מילה כמו "experience" (ברשימת `requirement_cues`, config:51) בפסקת "About us" גם היא מסמנת את המשפט כ-`kind="requirement"`, ולכן נכנס בכלל למנוע ה-extraction (extraction.py:111: `if span.kind != "requirement": continue`). זה מה שהופך את התרחיש לריאלי, לא תיאורטי בלבד. |
| **D6** | גבוה — clause משותף מאפשר ל"advantage" סמוך לבטל "must have" מפורש | [extraction.py:20,57-80,140,147](../cv_engine/domain/analysis/requirements/extraction.py#L20-L147) | `_SENTENCE=[.;\n]` לא חותך על פסיק; "Must have 5+ years..., European market an advantage." — אין parenthetical, אז ה-clause הוא כל המשפט; `"advantage"∈preferred_markers` (config:36) הופך את **כל** ה-clause, כולל ה-5+ שנים, ל-preferred | עצמאי | **CONFIRMED** ישירות מהרג'קס והקונפיג — `_SENTENCE` אינו כולל פסיק, ו-`_clause_around` (extraction.py:57-80) מחזיר את המשפט השלם פחות parentheticals כש-ה-match אינו בתוך aside. אותה א-סימטריה חוזרת ב-[interpretation.py:58-61](../cv_engine/domain/analysis/requirements/interpretation.py#L58-L61) בנתיב ה-AI, על ה-quote המצוטט. |
| **D9** | גבוה — כותרת ללא נקודתיים לא סוגרת section, בולט הטבות יורש `mandatory=True` | [segmentation.py:96-120](../cv_engine/domain/analysis/requirements/segmentation.py#L96-L120) (`_heading_section`), [segmentation.py:123-142](../cv_engine/domain/analysis/requirements/segmentation.py#L123-L142) (`_section_of`), [extraction.py:147](../cv_engine/domain/analysis/requirements/extraction.py#L147) | כותרת כמו "Perks"/"Benefits" (בלי `:`) שאינה matches מדויק לאף marker מוגדר מחזירה `None` מ-`_heading_section`; `None` לא סוגר section פתוח (רק heading לא-`None` משנה `section`) → הbulletים שתחתיה יורשים את ה-section הקודם. אם זה "requirements", בולט הטבות תמים שמזדמן להתאים ל-concept pattern מקבל `mandatory=True` ב-extraction.py:147 בלי אף מרקר | עצמאי; שלב 6 עם D5/D6 | **CONFIRMED** — עקבתי את `_segments` (segmentation.py:181-248) שורה-שורה: `section` משתנה רק ב-`if heading is not None: ...; section=heading` (שורה 219-226); heading=`None` פשוט `continue`-ת בלי לגעת ב-section. אין קוד שסוגר section על heading לא-מזוהה. |
| **D7** | בינוני — מדד מת, קבוע 1.0 בכל נתיב קיים | [confidence.py:48-57](../cv_engine/domain/analysis/requirements/confidence.py#L48-L57), [extraction.py:148-166](../cv_engine/domain/analysis/requirements/extraction.py#L148-L166) | `concept_classification_completeness` סופר `item.concept` לא-ריק; כל `ExtractedRequirement` נבנה תמיד עם `concept=concept.concept` (מחרוזת לא ריקה) — אין היום שום נתיב מייצר item ללא concept | Stage 8 (cleanup; ייתכן ותלוי בהחלטה #1 אם ייווצר נתיב חדש) | **CONFIRMED** — grep/read מלא של extraction.py לא מצא בנאי `ExtractedRequirement` עם `concept=""`/`None`. המדד קבוע מתמטית בקוד הנוכחי. |
| **D8** | בינוני — confidence מודד וקטור שלא קיבל את ההחלטה | [classification.py:336-348,414-418,453-454](../cv_engine/domain/analysis/classification.py#L336-L454) | הבחירה בפועל (`best()`) מדורגת לפי `(coverage_scores, term_scores)` — coverage קודם; אבל `top`/`second` שמוזנים ל-`classification_confidence` מגיעים אך ורק מ-`term_scores.most_common(2)` (שורה 416-418), בלי קשר ל-coverage | Stage 5 (אחרי שהדנומינטורים מתוקנים) | **CONFIRMED** — קראתי את כל `classify_job`; `ranking` (משמש להחלטה ול-ambiguity) ו-`top/second` (משמש ל-confidence) הם שני חישובים נפרדים לחלוטין מאותו טקסט. |
| **A1** | קריטי — נתיב AI לא יכול לגלות את באג הסגמנטציה | [analysis.py:234-241](../cv_engine/application/services/analysis.py#L234-L241), [ai_extraction.py:557-562,580-582](../cv_engine/domain/analysis/requirements/ai_extraction.py#L557-L582) | הספק מקבל `requirement_lines(job_text,...)` כ-hint; `by_ai` (understanding) ו-`extraction_is_failed` נמדדים מול **אותה** `requirement_lines()` — שורה שהסגמנטר לא מזהה (למשל תחת כותרת לא ב-`requirement_block_markers`) לא יכולה להוריד את `by_ai`, לא תדליק כשל, ולא תופיע כפער בשום מקום | תלוי Stage 0-2 (אותו קוד, לא תיקון נפרד) | **CONFIRMED** — אימתתי את כל שלוש נקודות הקריאה; אין שום נתיב אחר ב-ai_extraction.py שממדל את הטקסט המלא ללא תלות ב-`requirement_lines`. |
| **A2** | גבוה — confidence לא מחושב מחדש אחרי rebase | [classification.py:221-305](../cv_engine/domain/analysis/classification.py#L221-L305) (`rebase_requirements`), [analysis.py:280-295](../cv_engine/application/services/analysis.py#L280-L295) | `rebase_requirements`'s `model_copy(update={...})` מעדכן requirements/gaps/fit/fit_score/approval_reasons — **לא** confidence; לאחר מכן `merge_classification` עושה `min(deterministic.confidence, proposal.confidence)` על אותו confidence-לא-מעודכן | עצמאי (Stage 3) | **CONFIRMED** — קראתי את מילון ה-`update=` המלא ב-rebase_requirements (classification.py:289-304): אין מפתח `confidence`. עקבתי את הזרימה המלאה ב-analysis.py:280-328 — אין קריאה חוזרת ל-`extraction_confidence` אחרי rebase בשום מקום. |
| **A3** | גבוה — unmapped_statements נאסף, מאומת, ולא נקרא ע"י אף לוגיקת ניקוד | [ai_extraction.py:309-323,543-554](../cv_engine/domain/analysis/requirements/ai_extraction.py#L309-L554), [approval.py:197](../cv_engine/domain/analysis/approval.py#L197) | `unmapped_statement_ids()` מוגדרת ואף פעם לא נקראת (grep מלא בכל הפרויקט); `analysis.unmapped_statements` רק "עובר דרך" ב-merge_classification, לא נבדק ע"י שום approval reason או חישוב fit/confidence | תלוי Stage 0-2 (התיקון = לחווט את זה לרשימת ה-undetermined) | **CONFIRMED via grep**: `grep -rn "unmapped_statement_ids"` מחזיר רק את שורת ההגדרה. `grep -rn "\.unmapped_statements"` מחזיר רק "pass-through" ב-approval.py ו-האיסוף עצמו ב-ai_extraction.py — אין קורא שלישי. |
| **A4** | גבוה — extraction_is_failed הוא `any`, לא יחס | [ai_extraction.py:567-593](../cv_engine/domain/analysis/requirements/ai_extraction.py#L567-L593) | `return not any(...)` — מיפוי מוצלח של שורה אחת מתוך N מונע כישלון לגמרי, גם אם N=20 | שורש; Stage 1 | **CONFIRMED** ישירות מהקוד — אין שום סף יחס, `any()` בלבד. |
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
**צפוי:** אין להחזיר ירוק מלא בלי אף איתות על משרה עם תוכן שלא נקרא.
**בפועל:** `requirement_lines(text)==[]` → `fit_score=1.0`, `fit=HIGH`, אבל
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
**צפוי:** אין להחזיר ירוק מלא בלי אף איתות על משרה עם 2 בוליטי דרישה אמיתיים.
**בפועל (מאומת ידנית שורה-שורה):** `requirements=[]`, `extraction_confidence=1.0`
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
**צפוי:** `extraction_failed=True` (4 דרישות נאמרו, 0 הובנו) → `fit_score=None`,
`fit=UNKNOWN`, `approval_reasons` כולל `extraction-failed`.
**בפועל:** `confidence.py:94-95` מחזיר `False` לפני שבכלל בודק את ה-state → `fit_score=
fit_score_from_requirements([])=1.0`, `fit=HIGH`, ה-gap היחיד הוא warning (לא חוסם),
confidence≈`0.4×classification_confidence` (נמוך, אך fit עדיין 100%).

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

### A4
קלט:
```
Requirements:
- 5+ years of B2B sales experience
- Native-level English proficiency
- Strong negotiation and closing skills
- Comfortable working from our Tel Aviv office
```
4 requirement_lines (הרביעי נכנס כ-list-item תחת section="requirements", לא דרך cue),
רק הראשון ממופה. **צפוי:** קריאה של 1 מתוך 4 (25%) אמורה להיחשב חלקית/חשודה, לא "לא
נכשל" סתמי. **בפועל:** `extraction_is_failed` מחזיר `False` (`not any(...)` — מתקיים
כבר ע"י המיפוי היחיד), זהה בדיוק למה שהיה מחזיר גם על 1 מתוך 20 — אין רגישות ליחס.

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

## מה מתייתר אם החלטה #1 היא כן

("החלטה #1" = שורת דרישה שזוהתה כ-`requirement_line` אך לא מופתה לקונספט הופכת ל-
`Requirement(coverage="undetermined")` באותה רשימה ש-`fit_score` קורא.)

**נסגרים ישירות (הפתרון *הוא* ההחלטה, לא תיקון נוסף):**
- **A3** — חיווט `unmapped_statements`/`unmapped_statement_ids` לרשימת ה-undetermined
  הוא בדיוק התיקון; אין עוד עבודה מעבר לזה.
- חלק מ-**D3**'s הסימפטום (לא הבעיה כולה — ר' "נשארים פתוחים" למטה): denominator שכולל
  שורות שלא הובנו מקטין fit_score בפועל, לא רק completeness.

**נשארים פתוחים למרות זאת:**
- **D3 נשאר פתוח** — כפי שצוין, גם עם denominator מתוקן: הדוגמה `completeness≈0.56`
  שכבר מחושבת בטבלה למעלה (`(0.4+0.6·0.56)=0.736`) עדיין חוצה את `0.72/0.98≈0.735`.
  תיקון הדנומינטור מוריד completeness במקרים שהיו קודם מוסתרים לגמרי (D1-style), אבל
  אינו נוגע בבעיית כיול-הסף עצמה — זו נשארת שאלה נפרדת (החלטה #2 בהמשך המסמך).
- **D1 נשאר פתוח לגמרי** — הדוגמה שלו (שני בוליטים בעברית שלא מקבלים אף `kind`)
  אף פעם לא נכנסת ל-`requirement_lines()` מלכתחילה, כי הבעיה שם היא בסגמנטציה
  (`kind=None`), לא ב"זוהה אך לא מופתה". החלטה #1 פועלת רק על השלב השני; D1 דורש
  תיקון נפרד ב-Stage 1 (state `"absent"` מול `"unparsed"`).
- **D2 נשאר פתוח כבאג לוגי**, אך הסימפטום המסוכן שלו מוחלש מאוד: עם denominator
  מתוקן, `requirements` לא יהיה `[]` אלא רשימה של undetermined items → `fit_score_
  from_requirements` יחזיר `≈0.0`, לא `1.0`, גם כש-`extraction_failed` עדיין `False`
  בטעות. שווה לרשום את זה כ"משנה משמעות" (ר' למטה) ולא סתם "נשאר פתוח" — הכיוון
  הפוך מ-D7.
- **A1's סיכון השיורי** (ר' Stage 2 למעלה) נשאר — לא תלוי בהחלטה #1.
- **A2, A4, A11, D4, D5, D6, D9, A5-A10, C1, C2, D8** — כולם עצמאיים לחלוטין מהחלטה #1;
  שום דבר בהם לא נסגר או משתנה על ידה. D9 בפרט הוא באג בסגמנטציה (section לא נסגר),
  לא ב"זוהה אך לא מופתה" — אותה משפחה כמו D1, לא מושפע מהחלטה #1.

**משנים משמעות (לא "נסגר", לא "נשאר זהה" — המדד עצמו הופך לבעל תוכן):**
- **D7** — כרגע `concept_classification_completeness` קבוע מתמטית ל-1.0 כי כל
  `ExtractedRequirement` נבנה עם concept לא-ריק. ברגע שנוצרות ישויות `Requirement`
  עם `concept=None` (מדרישות שזוהו אך לא מופתו), המדד **מתחיל לזוז** בפועל בפעם
  הראשונה — אבל אז צריך לבדוק מחדש אם הנוסחה שלו (`sum(item.concept)/len(extracted)`)
  עדיין אומרת משהו נכון, כי היא נכתבה כשהיה בלתי אפשרי להזיז אותה. ייתכן שצריך
  ניסוח מחדש, לא רק "הפעלה".
- **D2** (ר' למעלה) — מ"מייצר fit=100% שגוי" ל"boolean שגוי בלי תוצאה מסוכנת בפועל".
  שווה עדיין לתקן את ה-boolean עצמו (Stage 1), אבל דחיפות התיקון יורדת אחרי Stage 2.

---

## Open product decisions (must be resolved before Stage 1 is coded)

1. **האם שורת דרישה שזוהתה כ-`requirement_line` אך לא הצליחה להתמפות לקונספט צריכה
   להפוך ל-`Requirement(coverage="undetermined", concept=None)` שנכנס לאותה רשימה
   ש-`fit_score_from_requirements` קורא?**
   המשמעות: כל requirement כזה יעלה `total_weight` באפס קרדיט (בדיוק כמו
   `unsupported`/`undetermined` היום), ויוריד את ה-fit_score בפועל, ויידלק
   `coverage-undetermined` שחוסם אישור. זו ההשלכה הישירה של docstring
   `fit_score_from_requirements` עצמו (gaps.py:53-60), שכבר מצהיר על הכוונה הזו אבל
   אין שום קוד שמייצר את ה-`Requirement` הזה מלכתחילה.
   *אם התשובה כן* — זה בעצם התיקון המשותף ל-D1 (חלקית), D3, A1, A3.
   *אם התשובה לא* — צריך מנגנון חלופי אחר לגמרי כדי לענות על אותה בעיה (למשל: לחסום
   אישור על סמך יחס `len(requirement_lines)` מול `len(requirements)` ישירות, בלי
   ליצור אובייקט Requirement מלאכותי).

2. **`extraction_failed`/`extraction_is_failed` — "any נקרא" מול "רוב נקרא":** מה סף
   סביר? (D1/D2/A4 דורשים תשובה קונקרטית: אחוז מינימלי, או ספירה מוחלטת, לפני
   שמכריזים על analysis כ"נכשל".) קשור לשאלה 1: אם undetermined נכנס לרשימה, ייתכן
   שה-fit_score עצמו (שיוצא נמוך מאוד כשרוב ה-denominator הוא undetermined) כבר
   "מעניש" מספיק, וניתן להשאיר את `extraction_failed` שמרני יותר (רק המקרה הקיצוני
   של 0 הבנה מוחלטת).

3. **`understood_elsewhere` (D2) — האם gap-כלל בודד (salesforce/crm/saas/וכו') אמור
   להספיק כדי לבטל `extraction_failed` על כל הפוסטינג, או רק על אותה דרישה
   הספציפית שהכלל מכסה?** הקוד הנוכחי מיישם את הפרשנות הרחבה ביותר (כל gap מבטל
   את הדגל הגלובלי).

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
