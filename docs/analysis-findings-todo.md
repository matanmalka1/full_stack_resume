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
enter the same list `fit_score` reads, at zero credit. `A1` requires no separate code
change beyond what Stage 1/2 already does to the deterministic path, because the AI
path calls the identical `requirement_lines()` function — verify with a regression test
instead of a new fix.

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

`D5`, `D6` — dedup-before-mandatory-computed, and a shared clause letting a nearby
"advantage" demote an explicit "must have" match.

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
| **D1** | קריטי — ירוק מלא, 0 approval reasons | [confidence.py:42-45,66-68,96](../cv_engine/domain/analysis/requirements/confidence.py#L42-L96), [gaps.py:62-63](../cv_engine/domain/analysis/gaps.py#L62-L63) | `requirement_lines(text)==[]` → `extraction_completeness` returns `None` → state `"absent"` (not `"unparsed"`) → `extraction_failed` returns `False` (only checks `state=="unparsed"`) → `fit_score_from_requirements([])==1.0` | שורש; מוזג עם D2/A4 בשלב 1 | **CONFIRMED** — קראתי כל שרשרת הקריאות; ההתנהגות תואמת בדיוק את התיאור, כולל ההודאה בדוקסטרינג של gaps.py:53-60 שהמנגנון סומך על `extraction_failed` להבחין בין "אין דרישות" ל"דרישות שלא זוהו" — הבחנה שלא קיימת בפועל בין `"absent"` ל־ track שהופך False. |
| **D2** | גבוה — extraction_failed מנוטרל ע"י gap-כלל יחיד | [classification.py:441-444](../cv_engine/domain/analysis/classification.py#L441-L444), [confidence.py:94-95](../cv_engine/domain/analysis/requirements/confidence.py#L94-L95), [gaps.py:262-270](../cv_engine/domain/analysis/gaps.py#L262-L270) | `understood_elsewhere=bool(rule_gaps)` → `if understood_elsewhere: return False` **לפני** even בדיקת ה-state — כלומר גם `state=="unparsed"` (שורות זוהו, 0 הובנו, לא רק "absent") מנוטרל | שורש; שלב 1 | **CONFIRMED, והיקף רחב מהמתואר**: קראתי `confidence.py:94-96` — ה-short-circuit קורה *לפני* חישוב ה-state בכלל, כך שהבאג לא מוגבל למקרה "0 requirements" (כפי שהדוגמה המקורית תיארה) אלא לכל מקרה שבו נמצא ולו gap-כלל אחד (salesforce/crm/saas/partnership/years-threshold) — גם אם 20 שורות דרישה זוהו ואף אחת לא הובנה. |
| **D3** | גבוה — סף האישור עובר בקריאה חלקית | [approval.py:14](../cv_engine/domain/analysis/approval.py#L14), [confidence.py:99-123](../cv_engine/domain/analysis/requirements/confidence.py#L99-L123), [classification.py:153-168,450-454](../cv_engine/domain/analysis/classification.py#L153-L168) | עם `classified=1.0` (ר' D7) והנוסחה `(0.4+0.6·completeness)·classified`, מספיק `completeness≈0.56` כדי לחצות `0.72/0.98≈0.735` | תלוי בהחלטת מדיניות #1 (Stage 0) + Stage 1/2 | **CONFIRMED** — שחזרתי את החשבון ישירות מהנוסחאות; מספרי הדוגמה (0.735, c≥0.558) עקביים עם קריאת הקוד, בהנחת `classification_confidence` גבוה טיפוסי. |
| **D4** | בינוני-גבוה — בולט עם 3 בקשות נספר כיחידת "הבנה" אחת | [confidence.py:14-25](../cv_engine/domain/analysis/requirements/confidence.py#L14-L25), [extraction.py:118-167](../cv_engine/domain/analysis/requirements/extraction.py#L118-L167), [segmentation.py:241](../cv_engine/domain/analysis/requirements/segmentation.py#L241) | `_understood` בודק חפיפת offset בין ה-`StatementLine` המלא (כל המשפט) לבין ה-`ExtractedRequirement.span` שהוא רק תת-מחרוזת שהרג'קס תפס — משפט אחד ארוך עם 3 דרישות, רק 1 חולצה, נספר כ"מובן" במלואו | עצמאי | **CONFIRMED** — `item.start`/`item.end` הם offsets של ה-regex match בלבד (extraction.py:141-165), לא של המשפט; `_understood` (confidence.py:21-25) סופר overlap ברמת ה-line, לא ברמת המושג. `segmentation.py:241` מוסיף אפקט נלווה: שורה שממשיכה משפט קודם (lowercase, ללא bullet) ממוזגת לאותה יחידה. |
| **D5** | גבוה — dedup קובע mandatory/preferred לפי המופע הראשון | [extraction.py:132-147](../cv_engine/domain/analysis/requirements/extraction.py#L132-L147), [requirements.json:43-68](../config/requirements.json#L43-L68) | דה-דופ (שורה 132-136, `concept`+`demanded`) רץ **לפני** חישוב mandatory/preferred (שורה 147) → אזכור ראשון תחת "About us" (preferred) "בולע" את המופע השני תחת "Requirements:" (mandatory) | עצמאי | **CONFIRMED, עם תנאי מוקדם שאומת**: cue-word matching ב-`_statement_kind` ([segmentation.py:169-171](../cv_engine/domain/analysis/requirements/segmentation.py#L169-L171)) הוא **ללא תלות בסקשן** — מילה כמו "experience" (ברשימת `requirement_cues`, config:51) בפסקת "About us" גם היא מסמנת את המשפט כ-`kind="requirement"`, ולכן נכנס בכלל למנוע ה-extraction (extraction.py:111: `if span.kind != "requirement": continue`). זה מה שהופך את התרחיש לריאלי, לא תיאורטי בלבד. |
| **D6** | גבוה — clause משותף מאפשר ל"advantage" סמוך לבטל "must have" מפורש | [extraction.py:20,57-80,140,147](../cv_engine/domain/analysis/requirements/extraction.py#L20-L147) | `_SENTENCE=[.;\n]` לא חותך על פסיק; "Must have 5+ years..., European market an advantage." — אין parenthetical, אז ה-clause הוא כל המשפט; `"advantage"∈preferred_markers` (config:36) הופך את **כל** ה-clause, כולל ה-5+ שנים, ל-preferred | עצמאי | **CONFIRMED** ישירות מהרג'קס והקונפיג — `_SENTENCE` אינו כולל פסיק, ו-`_clause_around` (extraction.py:57-80) מחזיר את המשפט השלם פחות parentheticals כש-ה-match אינו בתוך aside. אותה א-סימטריה חוזרת ב-[interpretation.py:58-61](../cv_engine/domain/analysis/requirements/interpretation.py#L58-L61) בנתיב ה-AI, על ה-quote המצוטט. |
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
