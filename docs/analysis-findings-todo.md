# Analysis/Classification Findings — Verification & Fix-Order TODO

Source: external review (Claude web) of the requirement extraction / classification /
fit-scoring pipeline, triggered by a real production record (`SuperFunnel` /
Account Executive, application `90787e94-1401-44ba-b8e3-ef4e8aecccde`) where
`fit_score=1.0` was computed from a single extracted requirement while
`confidence=0.429`. Every finding below was re-verified directly against the code in
this session (file:line cited), independent of the external review's own citations.

**התכנון נוחת בגלים.** נחתו: Stage 1+2, ‏3 (חלקית), ‏4, ‏5, ‏6, ‏7 (חלקית),
ו-C2 מ-Stage 8.
המסמך התכווץ פעם אחת: הפירוט של *איך* כל תיקון נחת עבר לדוקסטרינגים שליד הקוד,
ורפרודוקציות של ממצאים סגורים עברו לטסטים שמחזיקים אותן. מה שנשאר כאן הוא מה
שפתוח, מה שחוסם אותו, וההנמקה של כל הכרעה — כדי שלא תיפתח מחדש.

## מצב נוכחי (למי שממשיך מכאן)

‏23 ממצאים מאומתים (‏D1-D10, ‏A1-A12, ‏C1-C2; ‏A4 ו-D10 אינם באגים עצמאיים),
סדר תיקון ב-8 שלבים. ‏`A12` נוסף ב-Stage 3, מתוך היישום ולא מהסקירה המקורית.
**סגורים:** ‏D1, ‏D2, ‏D4, ‏D5, ‏D6, ‏D8, ‏D9, ‏D10, ‏A3, ‏A4, ‏A7, ‏A11, ‏A12, ‏C1,
‏C2, והחלטות ‏#1-#17.

**מה פתוח, ומה חוסם כל אחד:**

| פתוח | חסום על |
| --- | --- |
| **Stage 7** (`A5`, `A6`, `A8`, `A9`, `A10`) | **חלקית.** ‏`A7` ו-`A12` נחתו (#16, #17). נשארו: ציר 1 — `A5`, `A6`; ציר 2 — `A8`, `A10` (**#18** פתוחה, דורשת מדידה); ציר 3 — `A9`, שנשפט עם סמנטיקת coverage |
| **A2** | **הוכרע עקרונית** (#13-#15). נשאר תלוי ב-**#18**, בהפרדת שני תפקידי `mapped_spans`, ובחסם המבני (פרמטר/שדה חדש) |
| **D7** | ‏A2 — נסגר יחד איתו. #13 קבעה שאין אנלוג בנתיב ה-AI, ולכן הגורם ניתן להסרה |
| **D3** | כיול הסף `0.72` — אף החלטה שנפתרה לא נגעה בו |
| **A1** | סיכון מבני קבוע, לא נסגר ע"י שום שלב |

**‏Stage 7 נפתח ונחת חלקית.** ‏#16 ו-#17 הוכרעו ויושמו — `A12` ו-`A7` סגורים.
מה שנשאר בשלב: **ציר 1** — `A5` (‏`demanded`/`kind` של הספק נכנסים ל-
`threshold_coverage` בלי אימות מול הציטוט) ו-`A6` (ציטוט מ-`section == "other"`
מותיר את שני התנאים `False`); **ציר 2** — `A8` (הסתירה מול `system-v3.md:27-28`,
שתיקונה הזול הוא בפרומפט) ו-`A10`, שעליו **#18** פתוחה ודורשת מדידה על מודעות
אמת; **ציר 3** — `A9`, סמנטיקת coverage של `any-of`. **‏`A2` ו-`D7` מוכרעים
עקרונית** (#13-#15) וממתינים ל-**#18** ולשתי חתיכות העבודה המבנית שמתוארות תחת
#15: הפרדת שני תפקידי `mapped_spans`, והפרמטר/שדה החדש שהחסם המבני מחייב.
‏`D3` (כיול `0.72`) ו-`A1` (הסיכון המבני) אינם משויכים לשום שלב ונשארים פתוחים
בפני עצמם.

### מה נחת, ולמה — Stage 1+2, 3, 4, 5, 6, 7 (חלקית)

**הפירוט המלא של כל תיקון נמצא בדוקסטרינג של הפונקציה שהוא נגע בה**, שם הוא
נשמר ליד הקוד ולא יכול להיסחף ממנו. כאן רק ההכרעות עצמן, כדי שלא ייפתחו מחדש.

| שלב | ממצא | ההכרעה, בשורה |
| --- | --- | --- |
| 1+2 | **D1** | `fit_score=None` באתר הקריאה (`classify_job`/`rebase_requirements`), **לא** בתוך `fit_score_from_requirements` — החוזה שלה (`1.0` על רשימה ריקה) נכון בבידוד ולא נגעו בו. `gaps.py` לא נגע כלל |
| 1+2 | **D2** | ה-short-circuit של `understood_elsewhere` נמחק; `extraction_failed` הוא בדיוק `extraction_state(...) == "unparsed"` |
| 1+2 | **A3** | `verify_and_cover_extraction` בונה בעצמה `Requirement(undetermined)` לכל שורה לא-ממופה; `unmapped_statements` נשאר גילוי נלווה בלבד |
| 1+2 | **A4** | מוגדר-מחדש: המסגור של המסמך היה שגוי, לא הקוד. אחרי שישויות `undetermined` קיימות, ההפרש בין 1-מ-20 ל-20-מ-20 נישא ב-`fit_score`, וה-`any()` תמיד היה הצורה הנכונה לבוליאן קטסטרופה (החלטה #2) |
| 3 | **A11** | דה-דופ לפי `requirement_id`, **לא** ordinal פוזיציוני: השניים חלופיים, ו-ordinal היה נותן לשתי הצעות זהות שני ids ובכך *מנטרל* את הדה-דופ ומשאיר את ניפוח המכנה פתוח. `ordinal=0` נשאר קבוע במכוון |
| 4 | **D4** | מודדים לפי **בקשה** ולא לפי סטייטמנט — `statement_asks`, **בתוך המדד ולא בסגמנטר**. סגמנטר דק יותר היה מזיז את `requirement_lines` ואיתה את כל מה שתלוי בה, בלי שאף אחד מהם שואל שאלת גרנולריות; ולא היה מתקן את D4 בכלל, כי הבולט שהממצא נשען עליו הוא משפט אחד |
| 4 | **D10** | מוגדר-מחדש ואז נסגר. הפרמיסה התקיימה אחרי D4 והתשובה לא זזה (`0` במונה אינו תלוי במכנה); הכשל האמיתי היה **ווקבולרי** — התבנית דרשה `compan\w*` ליטרלית והמודעה אמרה "industry". התבנית הקיימת הורחבה (לא קונספט שני — אותה משמעות), `extraction_version` ‏`"2"→"3"` |
| 6 | **D5** | `mandatory` מחושב **לפני** הדה-דופ, ומופע mandatory **מחליף** מופע preferred שכבר נרשם — כולל ה-span וה-offsets, כי `mapped_spans` נגזר מהם: בלי זה הדרישה המפורשת נשארת מדווחת כשורה שלא נקראה. ‏`ordinal` של מופע שהוחלף אינו ממוחזר |
| 6 | **D6** | `_SENTENCE` נמחק; `_clause_around` חותך לפי `ask_bounds` — **הגדרה אחת** משותפת עם `extraction_completeness`. פסיק לבדו היה הופך את "Salesforce, a plus." ל-mandatory; `ask_bounds` נושא את השומרים (שבר קצר מ-`_MIN_STATEMENT`, ו-`\s+` עבור `3.5`). ‏`_ASK_BREAK` לא שונה, ולכן המכנה של D4 לא זז |
| 6 | **D9** | כותרת ערומה לא-מוגדרת פותחת `other` — מה ש-`Benefits:` כבר עושה; הנקודתיים שם טיפוגרפיה. ארבעה שומרים, והראשון הוא **ווקבולרי הדרישות עצמו** (`_statement_kind is None`), ולכן "SaaS experience preferred" לא נבלע |
| 6 | **#10** | נשקל מחדש אחרי D9, והתשובה **לא זזה**: `mandatory=False`. הנימוק הישן ("`section` שגוי") פג; החדש לא: הישות קיימת כי שום דבר לא קרא מה השורה מבקשת, ו-`mandatory=True` היה טוען חובה על דרישה שלא זוהתה |
| 5 | **D8** | הקלט ל-`classification_confidence` הוא הפרופיל **שנבחר** (`top = term_scores[profile]`, ‏`second` = הטוב שבאחרים), לא שני המובילים בווקבולרי. **הנוסחה והיחידה לא נגעו** — ההסתייגות המתועדת (הסקאלה כוילה למספרי-מונחים, coverage מרווה אותה) נשמרת במלואה; מה שהשתנה הוא הנושא. משמעות המספר: "כמה הווקבולרי תומך בהחלטה שהתקבלה", לא "כמה הווקבולרי הפריד" |
| 5 | **C1** | `low-confidence` מפוצל לפי **מי חוסם**: ‏`low-confidence-extraction` (`{analysis}`/`ANALYSIS_INCOMPLETE`) ו-`low-confidence-classification` (`{track,profile}`/`CLASSIFICATION_AMBIGUITY`). הגבול נגזר — `extraction_score < CONFIDENCE_APPROVAL_THRESHOLD / MAX_CLASSIFICATION_CONFIDENCE` — ולא כויל כקבוע חדש. הקוד הערום נשאר רשום ונפלט, לרשומות היסטוריות ול-`merge_classification` |
| 7 | **A12** | ההבטחה **והשדה** נמחקו. היו **שתי** הצהרות שקריות (השנייה נקבה ב-`coverage.py` כצרכן, והוא לא קורא אותו), `_strict_schema` חייב כל ספק לפלוט את השדה, הפרומפט מעולם לא ביקש אותו, ואין ווקבולר תגיות שמולו "זר" מוגדר. ‏`output_schema_version` עלה `"1.0.0"→"2.0.0"` |
| 7 | **A7** | הגדרה אחת (`_overlap`) לשתי השאלות; הבדיקה רצה מול **סטייטמנט-הבית** (חפיפה מרבית) במקום לדרוש הכלה וליפול מהלולאה בשקט. לא דחייה (כלל חדש שהפרומפט לא הודיע עליו) ולא כל-סטייטמנט-חופף (הידוק, בניגוד לכיוון של פריט 15) |
| 8 | **C2** | הדה-דופ המת נמחק. `gap.requirement` הוא תווית ש-`derive_gaps` כותבת, `requirement.text` הוא ספן מהמודעה — שוויון ביניהם צירוף מקרים, ומודעה שניסחה בולט כתווית הייתה **מאבדת** את ה-gap. ציר אמיתי דורש קונספט משותף, ולכללים אין |

**‏`fit=HIGH` של PAYME מעולם לא הורווח** — הוא בא מ-`requirements == []` ומ-
`fit_score_from_requirements([]) == 1.0`, כלומר ה-false green של D1 עצמו. הטסט
קיבע באג. `LOW` הוא התשובה הנכונה, כי מה שהמודעה מבקשת הוא גבול מוצהר של
המועמד (`sales.tech_sales.boundary`). **תקדים:** כשטסט מקבע מספר, לבדוק תמיד אם
המספר היה נכון מלכתחילה.

**מה שנשאר פתוח מתוך השלבים שנחתו:** `D3` (כיול הסף `0.72` — אף החלטה לא נגעה
בו) ו-**הסיכון השיורי של `A1`**: `by_ai` ו-`extraction_is_failed` נמדדים מול
`requirement_lines()` הדטרמיניסטי, לא מול מה שה-AI קרא, ולכן שורה שהסגמנטציה לא
מזהה נשארת בלתי-נראית לשני הנתיבים. זה סיכון **מבני קבוע**, לא תקלה שנסגרה.

### מה זז בפועל ב-Stage 5 — ערכים וקודים, כמצופה

**‏`confidence` זז בכל מודעה שבה הווקבולרי לא בחר את הפרופיל שנבחר**, ותמיד כלפי
מטה (‏`max(0, top − second)` מאפס את בונוס-המרווח כשהמרווח שלילי):

| פיקסצ'ר | פרופיל שנבחר | מוביל הווקבולרי | לפני | אחרי |
| --- | --- | --- | --- | --- |
| `REVIEW_DECISION_JOB` | tech-sales | account-manager (1) | 0.66 | 0.58 |
| `PAYME_TECH_SALES_JOB` | tech-sales | development (1) | 0.297 | 0.261 |
| `RIVERSIDE_JOB` | tech-sales | account-executive (1) | 0.37 | 0.3066 |
| `PARTLY_MAPPED_JOB` | tech-sales | account-executive (2) | 0.574 | 0.406 |

בכל ארבעתן `term_scores[profile] == 0` — כלומר המספר שדווח קודם לא היה "ודאות
נמוכה בהחלטה", הוא היה ודאות **בפרופיל אחר**. ‏`ACCOUNT_MANAGER_JOB` ו-`THIN_JOB`,
שבהן הווקבולרי והכיסוי מסכימים, לא זזו כלל — המקרה הראשון משלושת המקרים בהחלטה #5.

**ארבעה טסטים עודכנו לטענה החדשה, אף אחד לא "הוחזר" למספר ישן:**

- `test_accepting_an_incomplete_analysis_resolves_it_and_nothing_else` — קיבע
  ש-`low-confidence` **נשאר** אחרי `accept_incomplete_analysis`. אחרי C1 הקוד
  על מודעה לא-נקראת הוא `low-confidence-extraction`, ואותה קבלה **כן** עונה
  עליו: זו אותה טענה בדיוק ("ה-extraction הוא שמחזיק את השער"). ה-"nothing
  else" של הטסט נשאר — אף override של סיווג לא נוגע באף אחד משניהם.
- `test_deterministic_ambiguity_is_resolved_by_choosing_the_classification` —
  ‏`track_override` כבר לא מנקה את reason ה-confidence. זה C1 עצמו.
- `test_provider_cannot_relax_approval_confidence_or_language` — נחסם עכשיו
  קודם ע"י שער ה-completeness, שאינו הנושא שלו. **הפיקסצ'ר לא נגע**; הטסט עובר
  דרך `apply_analysis_decisions` בדיוק כמו משתמש, ואז מוודא שמה שחוסם הוא
  הסתירה בסיווג.
- `test_an_unreadable_posting_stays_blocked_after_the_classification_is_decided`
  (‏`test_state_projection.py`) — הדוקסטרינג שלו טען ש"מודעה שלא נקראה גם לא
  מקבלת confidence, וזו שאלה אחרת" ולכן מוקרן גם `MATERIAL_CLASSIFICATION_
  AMBIGUITY`. **זו בדיוק המסגור ש-C1 מבטל:** ה-confidence שם שקוע בחצי
  ה-extraction, ולכן מוקרן reason אחד בלבד.

**הכרעה אחת נדרשה מעבר למה שהמסמך כתב, ב-`merge_classification`.** הקוד שם היה
`if confidence < THRESHOLD: reasons.append("low-confidence")` על ה-`min`. אחרי
הפיצול, ניתוח דטרמיניסטי חלש כבר נושא את הקוד המיוחס שלו (יורש דרך
`reasons = list(deterministic.approval_reasons)`), וה-append היה מוסיף לצידו קוד
ערום שמשמעותו המתועדת היא "הספק הצהיר על אי-ודאות" — טענה על הספק שהספק לא
הצהיר. לכן התנאי הוא עכשיו `proposal.confidence < THRESHOLD`. **קבוצת הניתוחים
שנושאים reason כלשהו של confidence לא זזה**: `min(a,b)` מתחת לסף בדיוק כאשר אחד
מהם מתחת לסף. אין כאן שכפול של לוגיקת הפיצול, שהמסמך אסר — האתר הזה עדיין אינו
מפצל דבר, הוא רק מפסיק להעיד על מה שאינו רואה.

**מה לא נגע:** ‏`extraction_version` (‏D8/C1 אינם משנים סמנטיקת חילוץ ולא את זהות
`requirement_id`), הסף `0.72` עצמו (‏D3, פתוח), ומבנה `extraction_confidence`
(גבול A2 — `confidence.py` לא נגע כלל). התקרה `0.98` עלתה לקבוע בעל-שם
`MAX_CLASSIFICATION_CONFIDENCE` כי היא כעת חלק מהגדרת הגבול של C1, לא רק פרט
בנוסחה.

### מה נחת ב-Stage 7, ומה עוד לא

**‏`A12` — ההבטחה והשדה ירדו יחד.** ארבע עובדות הכריעו, וכולן נמצאו בקוד ולא
היו במסמך: ההצהרה השנייה נקבה ב-`coverage.py` כצרכן והוא לא קורא את השדה (שתי
הבטחות שקריות, לא אחת); `_strict_schema` הפך את השדה ל**חובה** בסכמה שנשלחה,
כלומר כל ספק חויב לפלוט תגיות מתות; הפרומפט מעולם לא ביקש תגיות; ואין ווקבולר
תגיות מוצהר שמולו "זר" מוגדר, כך שמימוש השער היה מתחיל בהמצאת ווקבולר. **מה
שנלקח במודע:** ‏`output_schema_version` עלה `"1.0.0"→"2.0.0"`, ו-`extra="forbid"`
אומר שספק שימשיך לשלוח `topic_tags` ייכשל ב-`INVALID_OUTPUT`. זה הכיוון הנכון:
השדה לא יחזור כנתון לפני שיחזור כהחלטה.

**‏`A7` — הבדיקה רצה עכשיו, במקום לדלג דווקא על המקרה שדרש אותה.** ‏`_overlap`
הוא הפרימיטיב היחיד; `_home_statement` בוחר לפי חפיפה מרבית; `_same_statement`
נשאר "כל סטייטמנט משותף" (‏context quote אמור להיות מותר להיות הכותרת שמעל
הבולט) אבל נשען על אותו פרימיטיב, ולכן השתיים לא יכולות להיסחף שוב.

**‏`label` תועד, ופריט מעקב 7 נסגר.** הוא נשאר בחוזה ואינו נקרא — מכוון, מאותו
נימוק שמעדיף `interpretation_identity_key` על `member_id` — וזה כתוב עכשיו
בדוקסטרינג במקום להיות ידע שבעל-פה.

**מה שלא נגעתי בו ב-Stage 7, במפורש:** ציר 1 עדיין מחזיק את `A5` (‏`demanded`/
`kind` נכנסים ל-`threshold_coverage` בלי אימות מול הציטוט) ואת `A6` (ציטוט
מ-`section == "other"` משאיר את שני התנאים `False`); ציר 2 מחזיק את `A8`
(שתיקונו הזול הוא בפרומפט) ואת `A10`, שעליו **#18** פתוחה ודורשת מדידה; וציר 3
מחזיק את `A9`. אף אחד מהם אינו חסום על #16/#17 — הם פשוט לא היו ב-delivery הזה.

### מה זז בפועל ב-Stage 6 — אפס, וזה היה הממצא

על כל 22 פיקסצ'רי המודעות ב-`tests/`, חמש התלויות שהמסמך דרש לדווח עליהן
(`extraction_completeness`, `unmatched_requirement_lines`, ה-`requirement_id` של
ישות סינתטית, `by_ai`/`extraction_is_failed`, ו-`seen`/`ordinal`) יצאו
**זהות לחלוטין**. לכן שום טסט קיים לא נשבר — **וזו לא הצלחה אלא ממצא: לקורפוס
לא הייתה שום כיסוי לאף אחד מ-D5/D6/D9.** משם נוספו טסטי הרגרסיה, ואומת ששלושת
טסטי הבאגים אדומים על הקוד שלפני התיקון. על קלטי הממצאים עצמם שלוש התלויות כן
זזו, בכיוון הנכון: D5 ו-D6 מחזירים `mandatory=True` לדרישות שנוסחו במפורש, ו-D9
מוריד `mandatory` מטקסט שמעולם לא היה דרישה ומוציא בולט הטבות מהמכנה.

### `extraction_version` הועלה `"3"` → `"4"`

**נדרש.** D5/D6/D9 משנים את ה-`mandatory` של דרישות ש-`requirement_id` שלהן היה
נשאר **זהה** (‏`mandatory` אינו בפיילואד של ה-id) — בדיוק מה שהדוקסטרינג של
`requirement_id` מצהיר שהשדה נועד למנוע. acceptance שנרשם כשהמנוע אמר "preferred"
היה עונה בשקט על "mandatory". **המחיר:** כל ה-ids בקורפוס ממופתחים מחדש. רשומות
שכבר נכתבו קפואות תחת `"2"`/`"3"` ולא נגעו (החלטה #8). **הנגיעה היחידה
ב-`config/requirements.json` היא שורת הגרסה** — אף פטרן, cue או marker לא שונה.

### מה נשאר מחוץ להיקף, במפורש

**‏D6 בנתיב ה-AI (`interpretation.py:55-72`) — לא נגעתי.** האסימטריה חוזרת שם:
`quoted` הוא ה-quote המלא, אין `_clause_around` כלל, ולכן ספק שמצטט את כל הבולט
מקבל `preferred=True` מ-"advantage" ששייך לחצי השני. **זהו שער על טענת ספק, לא
מדד** — הדומיין של Stage 7 ושל החלטה #4 — וכיוון התיקון שם הוא **הרפיית** שער,
כך שההנמקה של D6 ("הכיוון השמרני") אינה עוברת לשם. ר' פריט מעקב 15.

**‏D7 — תנאי עצירה, לא נגעתי.** הוא הגורם `classified` של `extraction_confidence`
(confidence.py:65 → 131) ועדיין קבוע `1.0` בכל נתיב קיים. נגיעה בו מכריעה את
שאלה 1 של A2 כתופעת לוואי. חסום עד ש-A2 נסגר.

**גבול A2 לא נגעו בו** — מבנה `extraction_confidence` זהה בייט-לבייט;
`confidence.py` לא נגע ב-Stage 6 כלל.


### A2 — למה נעצר (תנאי עצירה, לא עבודה שלא נעשתה)

**המסמך הגדיר את A2 כ"missing recompute call, לא שאלת מדיניות". זה לא מדויק,
ובדיקת הקוד מראה למה.** `confidence` הוא
`extraction_score × classification_score`. ה-rebase לא נוגע ב-Track/Profile,
אז החצי השני תקף; מה שמתיישן הוא `extraction_score` בלבד — הוא מתאר את
ה-extraction הדטרמיניסטי, בעוד ש-`requirements` שעל הרשומה הם של ה-AI.

`extraction_confidence` חתומה על `(text, extracted: list[ExtractedRequirement],
concepts, *, understood_elsewhere)`. **לנתיב ה-AI אין `list[ExtractedRequirement]`
בכלל** — `cover_ai_requirement` בונה אחד זמני בסניף ה-threshold בלבד, עם
`start=0/end=0` (ai_extraction.py:272), ואין ממנו רשימה. כדי לחשב מחדש צריך
להכריע שלוש שאלות שאף החלטה שנפתרה לא עונה עליהן:

1. **האם יש גורם `classified` בנתיב ה-AI, ומעל מה.** האנלוג היחיד ל-
   `concept_classification_completeness` הוא `Requirement.concept` — אבל השדה
   הזה הוא `None` **בכוונה** בשני מקרים שאינם כישלון סיווג: כל דרישה
   `compositional` (ai_extraction.py:248, `concept=None` ללא תנאי), וכל ישות
   סינתטית מ-Stage 2. אותה נוסחה מעל requirements של AI מודדת משהו אחר ממה
   שהיא מודדת דטרמיניסטית: דרישת any-of מאומתת היטב הייתה נספרת כ"הווקבולרי
   לא הצליח לסווג".
2. **ישויות undetermined סינתטיות — בפנים או בחוץ.** ל-completeness התשובה
   כבר כפויה וטובה: `by_ai / len(requirement_lines)` מוציא אותן מהמונה ומשאיר
   אותן במכנה, בדיוק צורת הנתיב הדטרמיניסטי, ו-`by_ai` כבר מחויב לזה במפורש
   (ומתקיים `len(lines) == by_ai + len(unmatched_lines)`). השאלה חיה **רק אם**
   שאלה 1 נענית בחיוב: אז אותן שורות נענשות פעמיים — פעם ב-completeness ופעם
   ב-`classified` (concept=None) — עונש כפול שהנתיב הדטרמיניסטי לעולם לא מטיל,
   כי שורה לא-ממופה מעולם לא נכנסת ל-`extracted` שלו.
3. **האם רצפת ה-0.4 של `understood_elsewhere` חלה בנתיב ה-AI.**
   `rebase_requirements` לא מתייעצת ב-`derive_gaps` במכוון (מתועד בדוקסטרינג
   שלה, D2). כך שעל extraction של AI שלא קרא כלום, ההכרעה היא בין 0.0 קשיח
   לבין העברת `bool(rule_gaps)` מ-`classify_job` פנימה כפרמטר מפורש רביעי.

**וחסם מבני מעל שלושתן:** גם בהינתן תשובות, `rebase_requirements` לא יכולה
לכתוב confidence חדש, כי מאוחסן רק ה**מכפלה**. `deterministic_confidence`/
`proposal_confidence` (contracts/analysis.py:243-244) מפצלים deterministic מול
ספק — **לא** extraction מול classification. כלומר A2 דורש פרמטר מפורש חדש או
שדה מאוחסן חדש, כלומר שינוי חתימה ציבורית — לא מפתח נוסף במילון ה-`update=`.
(`merge_classification`'s `min(...)` הוא צרכן במורד הזרם שרק מוריד; אינו אתר
הבאג.)

**סדר גודל, כדי שהמחיר של ההשהיה יהיה ברור:** מודעה עם 20 שורות דרישה,
ה-AI קרא 1, הדטרמיניסטי קרא 12. היום נשמר `0.4+0.6·0.6 = 0.76` כפול
ה-classification; החישוב מול מה שה-AI באמת קרא הוא `0.4+0.6·0.05 = 0.43`.
זהו פער אמיתי וגדול — A2 לא בוטל, הוא ממתין להכרעה.

**מה נדרש כדי לשחרר:** הכרעה בשלוש השאלות למעלה (מועמדות להפוך להחלטות
#13-#15), ובחירה בין פרמטר מפורש לשדה מאוחסן לחסם המבני.


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
3. **~~`mandatory` של ישות סינתטית~~ — נסגר ב-Stage 6.** נשקל מחדש אחרי ש-D9
   תוקן, וההכרעה נשארה `mandatory=False` — עם נימוק חדש שאינו תלוי באמינות
   `section`. ר' "מה נחת ב-Stage 6".
4. **~~D7 מתחיל לזוז.~~ שגוי — תוקן ב-Stage 4.**
   `concept_classification_completeness` חתומה על
   `list[ExtractedRequirement]`, לא על `list[Requirement]`, ו-
   `extract_requirements` בונה כל `ExtractedRequirement` עם
   `concept=concept.concept` (מחרוזת לא ריקה) תמיד. ישויות ה-`Requirement`
   עם `concept=None` שנוצרו ב-Stage 2 **לעולם אינן מגיעות אליה** (נבדק
   ב-grep: שני קוראים בלבד, `extraction_confidence` ו-טסט). **המדד עדיין
   קבוע 1.0 מתמטית בכל נתיב קיים**, בדיוק כפי ש-D7 תיאר מלכתחילה.
5. **~~D10 — `0 מתוך N` אינו מדד קטסטרופלי אמין כש-N הוא מספר פסקאות.~~
   נסגר ב-Stage 4 — הפרמיסה התקיימה, התשובה לא זזה, והכשל האמיתי התברר
   כווקבולרי; ר' "D10 — איך נסגר" בראש המסמך. הטקסט המקורי נשמר להקשר:**
   `PAYME_TECH_SALES_JOB` הוא קטע מודעה ריאליסטי שבו הסגמנטר מחזיר
   `requirement_line` יחיד עבור הפסקה השלמה. שום concept אינו ממפה אותה, ולכן
   `0/1` מדליק `requirements-unmapped` ו-`extraction-failed` בדיוק כמו `0/20`.
   זהו מופע של D4 ותלוי בתיקון גרנולריות Stage 4; הטסט האדום הוא
   `tests/test_selection.py::test_payme_tech_sales_selection_uses_job_evidence_and_business_presentations`.

### פריטי מעקב שנוספו ב-Stage 3

6. **`ProposedRequirement.topic_tags` — קודם לממצא מלא, `A12`.** לא פריט מעקב:
   התיעוד מבטיח שער שלא קיים בקוד. ר' שורתו בטבלת הממצאים ו-Stage 7.
7. **~~`ProposedRequirement.label` גם הוא אינו נקרא~~ — נסגר ב-Stage 7**
   (החלטה #16 נגעה באותו דוקסטרינג, וזה בדיוק מה שהפריט ביקש): הוא נשאר בחוזה,
   אינו נקרא, וזה כתוב שם עכשיו במפורש. הטקסט המקורי:
   **`ProposedRequirement.label` אינו נקרא** ב-`verify_and_cover_
   extraction`/`cover_ai_requirement` (הטקסט מגיע מה-quote המאומת). זה נראה
   מכוון ותואם את הנימוק של `interpretation_identity_key` מול `member_id`
   ("a provider-chosen label with no verification behind it"), ולכן נרשם
   כתיעוד-חסר ולא כבאג. כדאי לומר זאת במפורש בדוקסטרינג כש-Stage 7 נוגע בקובץ.
8. **הדה-דופ של A11 מותיר הצעה כפולה בלי הצהרה למשתמש.** ספק שהציע דרישה
   פעמיים מקבל היום קיפול שקט — נכון לניקוד, אבל "הספק הכפיל" הוא אות איכות
   שאף מקום לא רושם. אם ריבוי כפילויות יתברר כתסמין אמיתי, זה מועמד ל-reason
   או למונה ב-`UnderstandingSources`, לא לשינוי בדה-דופ עצמו.

### פריטי מעקב שנוספו ב-Stage 4

9. **נתיב ה-AI נשאר במדידה לפי סטייטמנט בזמן שהדטרמיניסטי עבר לבקשות.**
   `by_ai`, ‏`unmapped_statement_ids` ו-`extraction_is_failed` סופרים שורות
   מ-`requirement_lines`; `extraction_completeness` סופר בקשות. **לא יישרתי
   אותם בכוונה** — מה שנתיב ה-AI מדווח כ-completeness שלו הוא בדיוק שאלה 2 של
   A2, שפתוחה; יישור כאן היה מכריע אותה כתופעת לוואי. הדוקסטרינג של
   `unmapped_statement_ids` תוקנה כדי להפסיק להבטיח "the identical measure".
   **זה קלט חדש ל-A2** — כשהוא חוזר לשולחן, השאלה כבר לא "איזו מידה" אלא גם
   "באיזו יחידה".
10. **פסקת פרוזה עם cue יחיד מייצרת מכנה גדול של שברי-תיאור.** ב-PAYME,
    12 בקשות שרק האחרונה בהן היא דרישה; 11 האחרות הן תיאור תפקיד שנכנס
    למכנה כי cue אחד (`experience`) סיווג את כל הפסקה כ-`requirement_line`.
    אחרי שהווקבולרי הורחב (D10) המונה שם הוא `1`, ולכן `completeness` של
    PAYME הוא `1/12 ≈ 0.083` — כלומר ההשפעה כבר לא תיאורטית: 11 שברי תיאור
    מדללים דרישה אחת אמיתית. **זו החצי של הסגמנטציה — דרך (א)** —
    ובמכוון לא נעשתה ב-Stage 4. מדד להחלטה: אם מודעות פרוזה עם הבנה חלקית
    מתחילות ליפול מתחת לסף ה-`low-confidence`, זה הטריגר לשקול פיצול לפי
    משפט ב-`_segments`, מול ההערה ב-segmentation.py:232-241.
11. **`_MIN_STATEMENT` משרת עכשיו שתי החלטות שונות** — "שורה קצרה מדי כדי
    להיות סטייטמנט" ו-"קטע קצר מדי כדי להיות בקשה". זה מכוון (אותה שאלה
    בשני קני מידה) ומתועד ב-`statement_asks`, אבל אם אחד מהם יזדקק לכיול
    נפרד, זו הנקודה שבה הם צריכים להיפרד לשני קבועים.
12. **`extraction_version` עלה ל-`"3"` — כל `requirement_id` בקורפוס ממופתח
    מחדש.** רשומות שכבר נכתבו קפואות תחת `"2"` ולא נגעו. המשמעות המעשית:
    acceptance שנרשם מול ניתוח ישן לא יענה על ניתוח חדש של אותה מודעה — וזה
    בדיוק מה ש-versioning נועד לעשות, לא תקלה. אם יתברר שזה מייצר חיכוך על
    מודעות שעדיין בטיפול, זו נקודת החלטה ולא באג.
13. **`technology-company-sales-context` אינו ניתן לסיפוק** —
    `satisfied_by_fact_ids` ו-`satisfied_by_tags` ריקים שניהם, ולכן הקונספט
    לעולם `partial` ולעולם לא `met`. זה **מכוון** (`sales.tech_sales.boundary`
    הוא גבול מוצהר של המועמד, ו-`REVIEW_DECISION_JOB` מתועד כך במפורש), אבל
    זה גם הסיבה שכל מודעה שמבקשת מכירה בחברת טכנולוגיה מקבלת `fit` לכל היותר
    בינוני. ראוי לוודא שזו עדיין העמדה הרצויה כשנוגעים בכיול הסף (D3).

### פריטי מעקב שנוספו ב-Stage 6

14. **`extraction_version` הועלה פעמיים בשני שלבים רצופים (`"2"→"3"→"4"`).**
    כל העלאה ממפתחת מחדש את כל הקורפוס ומבטלת acceptances על מודעות שעדיין
    בטיפול — גם כשהמשמעות של אותה מודעה ספציפית לא זזה כלל (‏Stage 6: אפס
    מ-22 הפיקסצ'רים זזו). המנגנון גס מדי מכדי למפתח מחדש רק את המודעות
    שהושפעו, ואין היום חלופה. **מדד להחלטה:** אם העלאות נעשות תכופות ומייצרות
    חיכוך אמיתי, זו הנקודה לשקול ציר גרסה עדין יותר (למשל גרסה פר-קונספט
    ב-`requirement_id`, כך שהעלאה נוגעת רק בדרישות שהקונספט שלהן השתנה). לא
    לפעולה עכשיו — הרחבה של פריט 12.
15. **‏D6 לא תוקן בנתיב ה-AI, ולכן שתי ההגדרות של "קלוז" כבר לא מסכימות.**
    הנתיב הדטרמיניסטי קורא קוואליפייר מתוך ה-ask (‏`ask_bounds`); השער ב-
    `interpretation.py:55-72` קורא אותו מכל ה-quote. ספק שמצטט את הבולט השלם
    ב-"Must have 5+ years..., European market ... is an advantage." יקבל
    `preferred=True` ותידחה לו הצעת `mandatory` נכונה. זה **שער**, לא מדד,
    ולכן שייך ל-Stage 7 ולהחלטה #2 (עד כמה שער אמור להיות מחמיר) — ר' "מה
    נשאר מחוץ להיקף" בראש המסמך.
16. **בולט הטבות עדיין נספר במכנה, גם אחרי D9.** על הקלט של D9, השורה
    "Native English speakers get an extra paid day off every quarter" עברה
    ל-`section=="other"` ואיבדה את ה-`mandatory` — אבל היא **עדיין**
    `requirement_line`, כי `_statement_kind` נותן ל-cue לגבור על ה-section
    ("native" הוא cue). לכן היא עדיין מייצרת `Requirement` (‏`mandatory=False`,
    ‏warning gap) ועדיין במכנה. זו התנהגות **מכוונת ומתועדת** של
    `_statement_kind` ("a cue outranks the section, in both directions"),
    לא שארית של D9 — אבל זו הנקודה שבה כלל ה-cue משלם על עצמו. מדד להחלטה:
    אם בולטי הטבות שמזדמנים להכיל cue מתבררים כשכיחים, זו שאלת כיול של
    `requirement_cues`, לא של הסגמנטציה.

17. **~~‏`docs/spec/state-and-use-cases.md` §7 כבר לא תואם את `APPROVAL_REASONS`.~~
    נסגר ב-Stage 5.** §7 מנה תחת `ANALYSIS_INCOMPLETE` את `extraction-failed`
    ו-`coverage-undetermined` בלבד, בזמן ש-Stage 1+2 כבר הוסיף
    `requirements-absent` ו-`requirements-unmapped` תחת אותו `review_code`.
    הסחף קדם ל-C1; C1 הוסיף חמישי (`low-confidence-extraction`), והפסקה עודכנה
    למנות את כל החמישה. **הספק הוא הבעלים של הרשימה** לפי CLAUDE.md, ולכן היא
    נכתבה שם ולא הוסברה בשקט בקוד.
18. **מחלוקת בין coverage לווקבולרי אינה מדווחת.** `ambiguous-signals` נדלק על
    **תיקו** בדירוג; אחרי החלטה #5 המצב שבו ה-coverage בחר פרופיל אחד
    והווקבולרי דוחף לאחר מוריד את ה-confidence, אבל אף reason לא אומר *למה*.
    מועמד ל-reason נפרד אם יתברר כשכיח. לא לפעולה עכשיו. **נצפה בפועל
    ב-Stage 5:** ארבעה מהפיקסצ'רים (`REVIEW_DECISION`, ‏`PAYME`, ‏`RIVERSIDE`,
    ‏`PARTLY_MAPPED`) הם בדיוק המצב הזה — `term_scores[profile] == 0` בכולם —
    כלומר זו לא תופעה נדירה בקורפוס הקיים. המשתמש רואה היום confidence נמוך
    ו-`low-confidence-classification`, בלי שנאמר לו שהכיסוי והווקבולרי הצביעו
    על פרופילים שונים.

### פריטי מעקב שנוספו ב-Stage 5

19. **‏`approvalReasonLabels` בפרונט חסר תוויות לשלושת הקודים של Stage 1+2.**
    `frontend/src/features/preparation/model/analysisLabels.ts` מכיל תווית ל-
    `extraction-failed` אך **לא** ל-`requirements-absent`,
    ‏`requirements-unmapped` ו-`coverage-undetermined` — ולכן משתמש שנתקל בהם
    רואה קוד גולמי. המפה נבנתה במכוון כ-`Record<string,string>` פתוח שנופל חזרה
    לקוד עצמו, כך שזה לא שובר את המסך, אבל זה סחף שקדם ל-Stage 5 בדיוק כמו
    פריט 17. **Stage 5 הוסיף תוויות לשני הקודים שלו בלבד** ולא נגע בשלושת
    האחרים, כי הם מחוץ להיקף שלו. **מדד להחלטה:** זה תיקון של ארבע שורות; שווה
    לסגור עם הנגיעה הבאה בקובץ. אין היום גארד נגזר שיתפוס קוד חדש בלי תווית —
    הגארד `test_every_approval_reason_the_engine_records_is_registered` מכסה את
    ה-backend בלבד.

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

**`D1`, `D2`, `A3` and the denominator split have since landed** (Stage 1+2), and `A4`
turned out not to be a fourth way `extraction_failed` was gameable: once
`Requirement(coverage="undetermined")` entries exist, `fit_score` is what distinguishes
a 1-of-20 read from a 20-of-20 read, and `any()`-based catastrophic-only detection was
always the right shape for that boolean. The bug was in this document's framing of A4,
not in the code. **What the root cause above still describes accurately is `D3` and
`A1`** — the threshold calibration nobody has set, and the AI path's permanent
dependence on the deterministic segmenter.

## Fix order

Findings are grouped into stages. A stage should land, and its own focused tests pass,
before the next stage is attempted — per this repo's stage-gate rule (one stage per
session/PR, gates scoped to the affected frontend/backend behavior at delivery;
no automatic full suite). Within a stage, order is not significant.

### Stage 0 — Product decisions

Decisions #1-#15 are resolved; each carries its full reasoning in place under **Open
product decisions**. Still open: **#16**-**#18**, the three implementation forks #4's
split created, all inside Stage 7.

### Stages 1, 2, 3, 4, 5, 6 — landed

Their designs were written here before they shipped and are no longer the record: the
reasoning lives in the docstrings of the functions each one touched, and the findings
they closed are held by named tests. The decisions themselves are in the table under
"מה נחת, ולמה" at the top, one line each. What did *not* close with them, and is still
live, is `D3` (threshold calibration), `A1`'s residual structural risk, and `A2`.


### Stage 5 — Confidence-formula correctness — **landed**

Its stated precondition held: retuning a formula before its inputs are trustworthy is
wasted work, and Stages 1-4 and 6 landed first. Neither decision needed a new tuned
constant — #5 kept `classification_confidence`'s scale and changed only whose term
counts it is handed, and #6 derived its split point from
`CONFIDENCE_APPROVAL_THRESHOLD` and the formula's own ceiling, now
`MAX_CLASSIFICATION_CONFIDENCE`. `D8` and `C1` landed together, as one delivery: they
touch the same formula and the same approval gate. See "מה זז בפועל ב-Stage 5" at the
top for what moved and which tests were restated.

### Stage 7 — AI interpretation/attestation gate integrity — **partially landed**

These are about whether the *gate* can be satisfied by a claim the source text doesn't
support, not about scoring arithmetic. They were grouped last on the premise that they
share one strictness dial. **They do not** — decision #4 splits them onto three axes,
and two of the three ask no product question at all:

- **Axis 1 — the gate is weaker than its own documentation: `A5`, `A6`, `A7`, `A12`.**
  Tighten to what the contract already promises. No good-faith rejection is possible,
  because the promise is what the provider was told.
- **Axis 2 — the gate contradicts this system's own prompt: `A8`, `A10`.** These reject
  correct output *today*, so the empirical-evidence requirement the original framing
  raised lands here — and the status quo is already the failure mode.
- **Axis 3 — not a gate at all: `A9`.** `any-of` coverage semantics; judged with `D8`
  and `C1`.

**Landed:** `A12` and `A7`, under decisions #16 and #17 - see "מה נחת ב-Stage 7"
at the top. **Residual:** `A5` and `A6` on axis 1, `A8` and `A10` on axis 2 (with
decision **#18** still open and still wanting measurement on real postings), and
`A9` on axis 3. None of them was blocked by #16 or #17; they were simply not in
that delivery.

### Stage 8 — Cleanup — **C2 landed, D7 still blocked**

`D7`, `C2` — a completeness sub-score that is a mathematical constant under every
current code path, and a dedup check whose two sides can never produce equal strings.

- **`C2` — landed**, with Stage 6, as the finding itself predicted it could. Deleted
  as dead, per the recommended default, with the reasoning left in place of the code
  and the derived guard folded into `test_no_concept_shadows_a_legacy_rule_gap` rather
  than added beside it. See "מה נחת ב-Stage 6" at the top.
- **`D7` is blocked, and not by anything in Stage 8.** It *is*
  `extraction_confidence`'s `classified` factor, so removing, replacing, or
  reformulating it decides A2's open question 1 as a side effect — the exact thing
  A2's boundary forbids. Re-verified against the code in this session and untouched.

---

## Findings table

| id | חומרה | קבצים (file:line) | תרחיש הכשל | תלות | סטטוס אימות |
|----|--------|---------------------|--------------|------|----------------|
| **D1** | קריטי — ירוק מלא, 0 approval reasons | [confidence.py:42-45,66-68,96](../cv_engine/domain/analysis/requirements/confidence.py#L42-L96), [gaps.py:62-63](../cv_engine/domain/analysis/gaps.py#L62-L63) | `requirement_lines(text)==[]` → `extraction_completeness` returns `None` → state `"absent"` (not `"unparsed"`) → `extraction_failed` returns `False` (only checks `state=="unparsed"`) → `fit_score_from_requirements([])==1.0` | שורש; Stage 1, **עצמאי מהחלטה #1** (זה שינוי ל-`fit_score_from_requirements` עצמה, לא ל-`requirements` שהיא מקבלת). **תיקון:** תחזיר `None`, לא `1.0`, על רשימה ריקה — ר' פירוט ב-Stage 1 למעלה, כולל תופעת-הלוואי על משרות ריקות-דרישות באמת | **CONFIRMED** — קראתי כל שרשרת הקריאות; ההתנהגות תואמת בדיוק את התיאור, כולל ההודאה בדוקסטרינג של gaps.py:53-60 שהמנגנון סומך על `extraction_failed` להבחין בין "אין דרישות בכלל" ל"דרישות שלא זוהו". ההבחנה הזו לא קיימת בפועל: `extraction_failed` (confidence.py:96) בודק אך ורק `state=="unparsed"`; `state=="absent"` (0 שורות זוהו) עובר תמיד כ-`False`, בלי שום דרך להבדיל "משרה שבאמת לא מציבה דרישות" מ"משרה שהסגמנטר פשוט לא זיהה בה אף שורת דרישה". |
| **D2** | גבוה — extraction_failed מנוטרל ע"י gap-כלל יחיד | [classification.py:441-444](../cv_engine/domain/analysis/classification.py#L441-L444), [confidence.py:94-95](../cv_engine/domain/analysis/requirements/confidence.py#L94-L95), [gaps.py:262-270](../cv_engine/domain/analysis/gaps.py#L262-L270) | `understood_elsewhere=bool(rule_gaps)` → `if understood_elsewhere: return False` **לפני** even בדיקת ה-state — כלומר גם `state=="unparsed"` (שורות זוהו, 0 הובנו, לא רק "absent") מנוטרל | שורש; Stage 1. **תיקון (החלטה #3 RESOLVED):** מחיקת ה-short-circuit לגמרי; `understood_elsewhere` נשאר קלט ל-`extraction_confidence` בלבד (רצפת 0.4) | **CONFIRMED, והיקף רחב מהמתואר**: קראתי `confidence.py:94-96` — ה-short-circuit קורה *לפני* חישוב ה-state בכלל, כך שהבאג לא מוגבל למקרה "0 requirements" (כפי שהדוגמה המקורית תיארה) אלא לכל מקרה שבו נמצא ולו gap-כלל אחד (salesforce/crm/saas/partnership/years-threshold) — גם אם 20 שורות דרישה זוהו ואף אחת לא הובנה. |
| **D3** | גבוה — סף האישור עובר בקריאה חלקית | [approval.py:14](../cv_engine/domain/analysis/approval.py#L14), [confidence.py:99-123](../cv_engine/domain/analysis/requirements/confidence.py#L99-L123), [classification.py:153-168,450-454](../cv_engine/domain/analysis/classification.py#L153-L168) | עם `classified=1.0` (ר' D7) והנוסחה `(0.4+0.6·completeness)·classified`, מספיק `completeness≈0.56` כדי לחצות `0.72/0.98≈0.735` | Stage 1+2 (החלטה #1 **RESOLVED=YES**) — אך הסף `0.72` עצמו לא מושפע מהחלטות #1-#3 (אלה קבעו *איך* partial extraction מיוצג, לא *מה הסף* לאישור על ייצוג כזה); D3 נשאר שאלת כיול פתוחה, לא מכוסה ע"י אף החלטה שנפתרה | **CONFIRMED** — שחזרתי את החשבון ישירות מהנוסחאות; מספרי הדוגמה (0.735, c≥0.558) עקביים עם קריאת הקוד, בהנחת `classification_confidence` גבוה טיפוסי. |
| **D4** | בינוני-גבוה — בולט עם 3 בקשות נספר כיחידת "הבנה" אחת | [confidence.py:14-25](../cv_engine/domain/analysis/requirements/confidence.py#L14-L25), [extraction.py:118-167](../cv_engine/domain/analysis/requirements/extraction.py#L118-L167), [segmentation.py:241](../cv_engine/domain/analysis/requirements/segmentation.py#L241) | `_understood` בודק חפיפת offset בין ה-`StatementLine` המלא (כל המשפט) לבין ה-`ExtractedRequirement.span` שהוא רק תת-מחרוזת שהרג'קס תפס — משפט אחד ארוך עם 3 דרישות, רק 1 חולצה, נספר כ"מובן" במלואו | עצמאי | **CONFIRMED** — `item.start`/`item.end` הם offsets של ה-regex match בלבד (extraction.py:141-165), לא של המשפט; `_understood` (confidence.py:21-25) סופר overlap ברמת ה-line, לא ברמת המושג. `segmentation.py:241` מוסיף אפקט נלווה: שורה שממשיכה משפט קודם (lowercase, ללא bullet) ממוזגת לאותה יחידה. **סגור ב-Stage 4** — דרך (ב): `statement_asks` היא יחידת המדידה, הסגמנטציה לא נגעה. ר' "מה נחת ב-Stage 4". |
| **D10** | גבוה — פסקה ריאליסטית שלמה נספרת כ-N=1 ומדליקה כשל קטסטרופלי | [segmentation.py:181-248](../cv_engine/domain/analysis/requirements/segmentation.py#L181-L248), [confidence.py:42-96](../cv_engine/domain/analysis/requirements/confidence.py#L42-L96), [helpers.py:48-56](../tests/helpers.py#L48-L56) | `PAYME_TECH_SALES_JOB` נשמר כפסקה פיזית אחת ובה כמה משפטים ותיאור תפקיד לצד "Prefer inside Sales experience...". ה-cue `experience` מסווג את כל הפסקה כ-`requirement_line` יחיד; אף concept אינו ממפה אותה → `completeness=0/1`, `state="unparsed"`, ‏`requirements-unmapped` ו-`extraction-failed`. בוליאן החלטה #2 מבחין רק בין 0 ליותר מ-0 ואינו יכול לדעת ש-N=1 אינו דרישה יחידה אלא פסקה שלמה | תלוי D4; Stage 4 | **CONFIRMED** על הקלט הריאלי הקיים: `requirement_lines==1`, ‏`extracted==0`. הטסט האדום: `tests/test_selection.py::test_payme_tech_sales_selection_uses_job_evidence_and_business_presentations` (`fit=UNKNOWN` במקום `HIGH`). החלטה #2 (`0 מתוך N`) משמעותית רק לאחר ש-N מייצג דרישות ולא פסקאות. **הוגדר-מחדש ואז נסגר ב-Stage 4.** אחרי D4 ‏`N=12` בקשות ולא פסקה אחת, והתשובה נשארה `0/12` — כלומר `extraction_failed=True` היה הבוליאן **עובד**, לא נכשל. הכשל האמיתי היה בווקבולרי: התבנית דרשה `compan\w*` והמודעה אומרת "tech-related industry". התבנית הורחבה ו-`extraction_version` עלה ל-`"3"`; PAYME עכשיו `partial` ו-`fit=LOW`. ‏`HIGH` המקורי היה ה-false green של D1 ולא הורווח מעולם. ר' "D10 — איך נסגר". |
| **D5** | גבוה — dedup קובע mandatory/preferred לפי המופע הראשון | [extraction.py:132-147](../cv_engine/domain/analysis/requirements/extraction.py#L132-L147), [requirements.json:43-68](../config/requirements.json#L43-L68) | דה-דופ (שורה 132-136, `concept`+`demanded`) רץ **לפני** חישוב mandatory/preferred (שורה 147) → אזכור ראשון תחת "About us" (preferred) "בולע" את המופע השני תחת "Requirements:" (mandatory) | עצמאי | **CONFIRMED, עם תנאי מוקדם שאומת**: cue-word matching ב-`_statement_kind` ([segmentation.py:169-171](../cv_engine/domain/analysis/requirements/segmentation.py#L169-L171)) הוא **ללא תלות בסקשן** — מילה כמו "experience" (ברשימת `requirement_cues`, config:51) בפסקת "About us" גם היא מסמנת את המשפט כ-`kind="requirement"`, ולכן נכנס בכלל למנוע ה-extraction (extraction.py:111: `if span.kind != "requirement": continue`). זה מה שהופך את התרחיש לריאלי, לא תיאורטי בלבד.  ‏**סגור ב-Stage 6** — `mandatory` מחושב לפני הדה-דופ, ומופע mandatory מחליף מופע preferred שכבר נרשם. |
| **D6** | גבוה — clause משותף מאפשר ל"advantage" סמוך לבטל "must have" מפורש | [extraction.py:20,57-80,140,147](../cv_engine/domain/analysis/requirements/extraction.py#L20-L147) | `_SENTENCE=[.;\n]` לא חותך על פסיק; "Must have 5+ years..., European market an advantage." — אין parenthetical, אז ה-clause הוא כל המשפט; `"advantage"∈preferred_markers` (config:36) הופך את **כל** ה-clause, כולל ה-5+ שנים, ל-preferred | עצמאי | **CONFIRMED** ישירות מהרג'קס והקונפיג — `_SENTENCE` אינו כולל פסיק, ו-`_clause_around` (extraction.py:57-80) מחזיר את המשפט השלם פחות parentheticals כש-ה-match אינו בתוך aside. אותה א-סימטריה חוזרת ב-[interpretation.py:58-61](../cv_engine/domain/analysis/requirements/interpretation.py#L58-L61) בנתיב ה-AI, על ה-quote המצוטט.  ‏**סגור ב-Stage 6** — `_SENTENCE` נמחק; הקלוז נחתך לפי `ask_bounds`, הגדרה אחת משותפת עם ה-completeness. הנתיב ה-AI (`interpretation.py`) נשאר מחוץ להיקף במפורש — פריט מעקב 15. |
| **D9** | גבוה — כותרת ללא נקודתיים לא סוגרת section, בולט הטבות יורש `mandatory=True` | [segmentation.py:96-120](../cv_engine/domain/analysis/requirements/segmentation.py#L96-L120) (`_heading_section`), [segmentation.py:123-142](../cv_engine/domain/analysis/requirements/segmentation.py#L123-L142) (`_section_of`), [extraction.py:147](../cv_engine/domain/analysis/requirements/extraction.py#L147) | כותרת כמו "Perks"/"Benefits" (בלי `:`) שאינה matches מדויק לאף marker מוגדר מחזירה `None` מ-`_heading_section`; `None` לא סוגר section פתוח (רק heading לא-`None` משנה `section`) → הbulletים שתחתיה יורשים את ה-section הקודם. אם זה "requirements", בולט הטבות תמים שמזדמן להתאים ל-concept pattern מקבל `mandatory=True` ב-extraction.py:147 בלי אף מרקר | עצמאי; שלב 6 עם D5/D6 | **CONFIRMED** — עקבתי את `_segments` (segmentation.py:181-248) שורה-שורה: `section` משתנה רק ב-`if heading is not None: ...; section=heading` (שורה 219-226); heading=`None` פשוט `continue`-ת בלי לגעת ב-section. אין קוד שסוגר section על heading לא-מזוהה.  ‏**סגור ב-Stage 6** — כותרת ערומה לא-מוגדרת פותחת `other` תחת ארבעה תנאים, שהראשון בהם (`_statement_kind is None`) הוא הווקבולרי עצמו ולכן מונע את הבליעה ההפוכה. |
| **D7** | בינוני — מדד מת, קבוע 1.0 בכל נתיב קיים | [confidence.py:48-57](../cv_engine/domain/analysis/requirements/confidence.py#L48-L57), [extraction.py:148-166](../cv_engine/domain/analysis/requirements/extraction.py#L148-L166) | `concept_classification_completeness` סופר `item.concept` לא-ריק; כל `ExtractedRequirement` נבנה תמיד עם `concept=concept.concept` (מחרוזת לא ריקה) — אין היום שום נתיב מייצר item ללא concept | Stage 8 (cleanup; ייתכן ותלוי בהחלטה #1 אם ייווצר נתיב חדש) | **CONFIRMED** — grep/read מלא של extraction.py לא מצא בנאי `ExtractedRequirement` עם `concept=""`/`None`. המדד קבוע מתמטית בקוד הנוכחי. |
| **D8** | בינוני — confidence מודד וקטור שלא קיבל את ההחלטה | [classification.py:336-348,414-418,453-454](../cv_engine/domain/analysis/classification.py#L336-L454) | הבחירה בפועל (`best()`) מדורגת לפי `(coverage_scores, term_scores)` — coverage קודם; אבל `top`/`second` שמוזנים ל-`classification_confidence` מגיעים אך ורק מ-`term_scores.most_common(2)` (שורה 416-418), בלי קשר ל-coverage | Stage 5 — **סגור** | **CONFIRMED** — קראתי את כל `classify_job`; `ranking` (משמש להחלטה ול-ambiguity) ו-`top/second` (משמש ל-confidence) היו שני חישובים נפרדים לחלוטין מאותו טקסט.  ‏**סגור ב-Stage 5** — הקלט הוא הפרופיל שנבחר; הנוסחה, הסקאלה והיחידה לא נגעו. ר' "מה זז בפועל ב-Stage 5". |
| **A1** | קריטי — נתיב AI לא יכול לגלות את באג הסגמנטציה | [analysis.py:234-241](../cv_engine/application/services/analysis.py#L234-L241), [ai_extraction.py:557-562,580-582](../cv_engine/domain/analysis/requirements/ai_extraction.py#L557-L582) | הספק מקבל `requirement_lines(job_text,...)` כ-hint; `by_ai` (understanding) ו-`extraction_is_failed` נמדדים מול **אותה** `requirement_lines()` — שורה שהסגמנטר לא מזהה (למשל תחת כותרת לא ב-`requirement_block_markers`) לא יכולה להוריד את `by_ai`, לא תדליק כשל, ולא תופיע כפער בשום מקום | Stage 1+2 (החלטות #1-#3 **RESOLVED**), עם תנאי מפורש ש-Stage 2 מיושם בנתיב ה-AI עצמו (ר' Stage 2 למעלה) — הסיכון השיורי (סגמנטציה שלא מזהה שורה מלכתחילה) נשאר גם אז, ר' Stage 2 | **CONFIRMED** — אימתתי את כל שלוש נקודות הקריאה; אין שום נתיב אחר ב-ai_extraction.py שממדל את הטקסט המלא ללא תלות ב-`requirement_lines`. |
| **A2** | גבוה — confidence לא מחושב מחדש אחרי rebase | [classification.py:221-305](../cv_engine/domain/analysis/classification.py#L221-L305) (`rebase_requirements`), [analysis.py:280-295](../cv_engine/application/services/analysis.py#L280-L295) | `rebase_requirements`'s `model_copy(update={...})` מעדכן requirements/gaps/fit/fit_score/approval_reasons — **לא** confidence; לאחר מכן `merge_classification` עושה `min(deterministic.confidence, proposal.confidence)` על אותו confidence-לא-מעודכן | עצמאי (Stage 3) — **נעצר, פתוח** | **CONFIRMED** — קראתי את מילון ה-`update=` המלא ב-rebase_requirements (classification.py:289-304): אין מפתח `confidence`. עקבתי את הזרימה המלאה ב-analysis.py:280-328 — אין קריאה חוזרת ל-`extraction_confidence` אחרי rebase בשום מקום. **עדכון Stage 3: ההגדרה "באג פשוט, לא שאלת מדיניות" הופרכה** — `extraction_confidence` חתומה על `list[ExtractedRequirement]` שאין בנתיב ה-AI, ותיקון דורש שלוש הכרעות מוצר פתוחות ועוד שינוי חתימה/סכמה. ר' "A2 — למה נעצר" בראש המסמך. |
| **A3** | גבוה — unmapped_statements נאסף, מאומת, ולא נקרא ע"י אף לוגיקת ניקוד | [ai_extraction.py:309-323,543-554](../cv_engine/domain/analysis/requirements/ai_extraction.py#L309-L554), [approval.py:197](../cv_engine/domain/analysis/approval.py#L197) | `unmapped_statement_ids()` מוגדרת ואף פעם לא נקראת (grep מלא בכל הפרויקט); `analysis.unmapped_statements` רק "עובר דרך" ב-merge_classification, לא נבדק ע"י שום approval reason או חישוב fit/confidence | Stage 2 (החלטה #1 **RESOLVED=YES**) — התיקון *הוא* חיווט זה, בתנאי המפורש שנוסף ל-Stage 2: `verify_and_cover_extraction` עצמה בונה `Requirement(undetermined)` לכל שורה לא-ממופה, לא רק שומרת unmapped_statements בצד | **CONFIRMED via grep**: `grep -rn "unmapped_statement_ids"` מחזיר רק את שורת ההגדרה. `grep -rn "\.unmapped_statements"` מחזיר רק "pass-through" ב-approval.py ו-האיסוף עצמו ב-ai_extraction.py — אין קורא שלישי. |
| **A4** | **מוגדר-מחדש — לא באג עצמאי.** הממצא המקורי (וההגדרה שלו כ"שורש") היה שגוי, לא הקוד | [ai_extraction.py:567-593](../cv_engine/domain/analysis/requirements/ai_extraction.py#L567-L593) | `return not any(...)` — מיפוי מוצלח של שורה אחת מתוך N מונע `extraction_is_failed`, גם אם N=20. **זו ההתנהגות הנכונה לפי החלטה #2** (בוליאני לכשל קטסטרופלי בלבד, לא מדד שלמות); ההבדל בין 1/20 ל-20/20 אמור להיות מיוצג ב-`fit_score` (דרך `undetermined` requirements, החלטה #1), לא בבוליאני הזה | **תלוי Stage 1+2 בשני הנתיבים** (ר' התנאי המפורש ב-Stage 2 למעלה) — עד ש-Stage 2 נוחת בנתיב ה-AI במפורש (לא רק הדטרמיניסטי), ה-1/20 עדיין בלתי-מיוצג שם לגמרי, וזה עדיין false-green בפועל — רק שהוא כבר לא "A4 צריך תיקון", אלא "Stage 2 טרם נחת בנתיב ה-AI" | **CONFIRMED שהקוד עושה בדיוק את זה** (`any()` ללא סף יחס) — **אך התיקון המוצע בגרסה הקודמת של המסמך (סף יחס) שגוי**; אין צורך בו, ר' החלטה #2 RESOLVED וההסבר ב-Stage 1. |
| **A5** | גבוה — demanded/kind מהספק לא מאומתים מול הציטוט | [ai_extraction.py:265-280](../cv_engine/domain/analysis/requirements/ai_extraction.py#L265-L280), [interpretation.py](../cv_engine/domain/analysis/requirements/interpretation.py) (כל הקובץ) | `cover_ai_requirement` מזין `demanded=demanded` (מהספק) ישירות ל-`threshold_coverage`; `verify_interpretation` בודק source_role/obligation/composition/members/negation — **לא** `demanded`, לא `kind` | Stage 7 | **CONFIRMED**: קראתי את כל `interpretation.py` — אין שום אזכור של `demanded` או `kind` בקובץ. ציטוט מאומת בת-byte של "10+ years" עם `demanded="2"` שנשלח ע"י הספק יעבור ללא בדיקה. |
| **A6** | גבוה — שער חד-כיווני: אפשר לרומם ל-requirement, אי אפשר להכחיש | [interpretation.py:52-71](../cv_engine/domain/analysis/requirements/interpretation.py#L52-L71) | הלולאה (שורה 54-56) בודקת רק "אם ה-section אומר mandatory/preferred, אסור לסתור" — לציטוט מ-section `"other"` (בלוק הטבות) שני התנאים (`preferred`, `mandatory`) הם `False`, אז שום exception לא נזרק, ללא קשר למה שהספק הצהיר | Stage 7 | **CONFIRMED** ישירות מהלוגיקה — עקבתי את שני ה-if-ים; אף אחד לא תלוי ב-`interpretation.source_role`/`obligation` כשה-section הוא `"other"`. הבדיקה בשורות 87-96 (`obligation=="mandatory" and source_role!="requirement"`) גם לא תופסת את המקרה כי היא דורשת אי-התאמה בין obligation ל-source_role, לא בין source_role לתוכן בפועל. |
| **A7** | בינוני — ציטוט שחוצה גבול-statement מדלג על הבדיקה בשקט | [interpretation.py:52-56,175-195](../cv_engine/domain/analysis/requirements/interpretation.py#L52-L195) | `for statement in _segments(...): if not (contained): continue` — אם אף statement לא מכיל את הספן במלואו, הלולאה מסתיימת בלי לבדוק דבר (לא raise, לא flag) | Stage 7 — **סגור** | **CONFIRMED** — קראתי את הלולאה; אין `else`/fallback אחרי שהלולאה מסתיימת ללא match. אימתתי גם את האי-עקביות מול `_same_statement` (שורה 190-195) שמשתמשת בחפיפה (overlap) ולא בהכלה (containment) — שתי פונקציות שונות לאותה שאלה.  ‏**סגור ב-Stage 7** (החלטה #17) — `_overlap` אחד, `_home_statement` לפי חפיפה מרבית. |
| **A8** | בינוני — דרישת ייחודיות ל-context_quote מתנגשת עם הנחיית הפרומפט עצמו | [interpretation.py:130-156](../cv_engine/domain/analysis/requirements/interpretation.py#L130-L156), [system-v3.md:27-28](../ai/prompts/system-v3.md#L27-L28) | הפרומפט מנחה: "unless you quote an explicit mandatory marker ('must','required','חובה') in context_quote"; ה-gate דוחה `context_quote` שמופיע יותר מפעם אחת בטקסט המלא — מילים כמו "must"/"required" חוזרות כמעט תמיד במודעת עבודה אמיתית | Stage 7 | **CONFIRMED**: קראתי את `system-v3.md` ואת `_verify_context_quote_occurs` (interpretation.py:148-156, `source_text.find(quote, first+1) != -1` → raise). זו סתירה מובנית בין ההנחיה לספק לבין המדיניות שאוכפת אותה, לא תלוית-תרחיש ספציפי. |
| **A9** | בינוני — any-of: חבר חלש-משמעות מנצח את הדרישה כולה | [ai_extraction.py:209-237](../cv_engine/domain/analysis/requirements/ai_extraction.py#L209-L237) | `"matched" if "matched" in member_coverages"` — אין בדיקה שהחבר שהתאים הוא זה שנושא את עיקר הדרישה | Stage 7 | **CONFIRMED** ישירות מהקוד. |
| **A10** | בינוני — כיוון הפוך: ≥2 concepts תואמים ⇒ undetermined, גם בציטוט "טבעי" | [ai_extraction.py:56-71](../cv_engine/domain/analysis/requirements/ai_extraction.py#L56-L71) | `concept_for_quote` מחזיר `None` (⇒ undetermined) כש-יותר מקונספט אחד תואם — בולט שלם עם 3 מושגים (בדיוק מה שהפרומפט מבקש לצטט) נופל תמיד | Stage 7 | **CONFIRMED** ישירות מהקוד — `matches[0] if len(matches)==1 else None`. |
| **A11** | גבוה — ordinal=0 קבוע ⇒ ID כפול ⇒ ניפוח מכנה | [ai_extraction.py:520-528](../cv_engine/domain/analysis/requirements/ai_extraction.py#L520-L528) | `ordinal=0` בכל שורה; `requirement_id` נבנה מ-hash של interpretation+kind+demanded+identity_span+ordinal — הצעה כפולה (אותו quote+interpretation) מייצרת שני `Requirement` שונים ברשימה עם **אותו** requirement_id, בלי דה-דופ | Stage 3 — **סגור** | **CONFIRMED** — קראתי את `verify_and_cover_extraction`: אין שום בדיקת ייחודיות על `req_id`/span לפני `requirements.append(...)`. **תוקן ב-Stage 3:** דה-דופ לפי `requirement_id` לפני ה-append, `ordinal=0` נשאר קבוע במכוון, `mapped_spans` ממשיך לקלוט גם כפולות. הנימוק המלא, כולל למה *לא* ordinal, בראש המסמך. |
| **A12** | גבוה — דוקסטרינג מבטיח שער שלא קיים; `topic_tags` מתקבל ולא נקרא | [ai_extraction.py:11](../cv_engine/domain/analysis/requirements/ai_extraction.py#L11), [contracts/providers.py:38-48](../cv_engine/domain/contracts/providers.py#L38-L48) | שני דוקסטרינגים מצהירים ש-`topic_tags` נקרא ואף אוכף: "consulted only as a boundary-association hint" ו-"a hint to fact-boundary association, **not a grant: a foreign tag disqualifies the proposal** rather than being trusted as scoping". בפועל השדה מתקבל מהספק, נשמר בחוזה, **ואף שורת קוד לא קוראת אותו** — כולל השער המובטח. ספק שמצרף tag זר לא נדחה ולא מסומן | Stage 7 — **סגור** | **CONFIRMED via grep** — `grep -rn "topic_tags" cv_engine ai config` מחזיר בדיוק שלוש שורות: שתי ההצהרות בדוקסטרינגים והגדרת השדה עצמה (providers.py:48). אין קורא רביעי. **חמור מ-A3:** ב-A3 פונקציה (`unmapped_statement_ids`) הוגדרה ולא נקראה — קוד מת, שקוף למי שקורא. כאן התיעוד מבטיח הגנה אקטיבית, כך שקורא הקובץ מאמין שיש שער שאין. **התיקון הוא הכרעה, לא שורה:** או לממש את השער שהדוקסטרינג מבטיח, או למחוק את ההבטחה (ואולי את השדה) — שתי הדרכים לגיטימיות, ואסור להשאיר את הפער. נמצא תוך יישום A11 (Stage 3), לא בסקירה המקורית. |
| **C1** | בינוני — האזהרה שכן נדלקה (low-confidence) ניתנת לביטול בטעות | [approval.py:52-76](../cv_engine/domain/analysis/approval.py#L52-L76) | `"low-confidence": ApprovalReason(frozenset({"track","profile"}), ...)` — בחירת Profile מנקה אזהרת confidence נמוך גם כשהסיבה האמיתית היא extraction_score נמוך, לא classification | Stage 5 — **סגור** | **CONFIRMED** מהטבלה עצמה — ואימתתי שההערה הפנימית בקוד (שורות 65-67) חלה ניסוחית בדיוק על `extraction-failed` בלבד, לא הורחבה ל-`low-confidence` שסובל מאותה בעיה.  ‏**סגור ב-Stage 5** — שני קודים חדשים, גבול נגזר, והקוד הערום נשאר לשני תפקידיו. |
| **C2** | בינוני — dedup בין rule-gap ל-requirement-gap כמעט אף פעם לא תואם | [classification.py:461-465](../cv_engine/domain/analysis/classification.py#L461-L465) | `covered_text = {requirement.text ...}` מול `gap.requirement` (תווית כתובה ביד כמו `"Salesforce"`, `"Direct SaaS Sales preference"`) — אין קונספט בשם salesforce/saas ב-`requirements.json`, כך שהמחרוזות האלה לעולם לא ייווצרו כ-`requirement.text` | Stage 8 | **CONFIRMED**: סרקתי את כל `config/requirements.json` — אין concept בשם salesforce/saas; המחרוזות היחידות שיכולות להגיע ל-`requirement.text` הן span-ים שחולצו מהטקסט (via `item.span`/`normalize_span`), לא התוויות הקבועות מ-`derive_gaps`.  ‏**סגור ב-Stage 6** — נמחק כקוד מת, עם הנמקה במקום הקוד וגארד נגזר ב-`test_no_concept_shadows_a_legacy_rule_gap`. |

---

## בדיקות אדומות — לממצאים הפתוחים

לכל ממצא פתוח: קלט קונקרטי, הערך הצפוי (מה שהמערכת *אמורה* להחזיר לפי הכוונה המוצהרת
בקוד/בדוקסטרינג), והערך שמתקבל היום בפועל. רוב הבדיקות הן קטע טקסט משרה שעובר דרך
`classify_job`. כשמדובר בבאג שדורש שני שלבים (deterministic → AI rebase) או פרופוזל
מדומה מספק, זה כתוב במפורש — אלה עדיין טסטים יחידה תקינים, רק לא מסוג "טקסט משרה
יחיד", ומצוין למה.


**ממצאים סגורים — הרפרודוקציה שלהם היא עכשיו טסט, לא פסקה.** הטסט הוא הרשומה;
העתק במסמך היה נסחף ממנו. הסעיפים שלמטה הם של הממצאים **הפתוחים** בלבד.

| ממצא | הטסט שמחזיק אותו |
| --- | --- |
| **D1** | `tests/test_analysis.py::test_fit_score_is_perfect_for_an_empty_requirement_list + ::test_a_fully_undetermined_analysis_scores_zero_not_high` |
| **D2** | `tests/test_analysis.py::test_a_local_rule_hit_no_longer_clears_a_failed_extraction` |
| **D4** | `tests/test_analysis.py::test_one_bullet_stating_three_things_is_not_understood_by_reading_one` |
| **D10** | `tests/test_selection.py::test_payme_tech_sales_selection_uses_job_evidence_and_business_presentations` |
| **D5** | `tests/test_analysis.py::test_a_required_restatement_outranks_a_passing_mention (+ ::test_a_preferred_restatement_does_not_demote_a_requirement)` |
| **D6** | `tests/test_analysis.py::test_a_comma_separates_two_demands_and_their_qualifiers (+ ::test_a_trailing_qualifier_too_short_to_be_a_demand_attaches_backwards)` |
| **D9** | `tests/test_analysis.py::test_an_unconfigured_bare_heading_still_closes_the_block_above_it (+ ::test_a_bare_requirement_is_never_read_as_a_heading_even_after_a_break, ::test_a_bare_heading_needs_a_break_above_it)` |
| **A3** | `tests/test_ai_tasks.py — the splice in verify_and_cover_extraction` |
| **A4** | `מוגדר-מחדש, אין קוד לתקן — ר' שורתו בטבלה` |
| **A11** | `tests/test_ai_tasks.py::test_a_requirement_proposed_twice_is_one_requirement (+ ::test_one_statement_proposed_twice_is_read_once)` |
| **C2** | `tests/test_analysis.py::test_no_concept_shadows_a_legacy_rule_gap — הגארד הנגזר` |
| **D8** | `tests/test_analysis.py::test_confidence_measures_the_vocabulary_behind_the_profile_that_was_chosen` |
| **C1** | `tests/test_analysis.py::test_a_confidence_the_extraction_sank_is_not_cleared_by_naming_a_profile (+ ::test_a_confidence_the_classification_sank_is_cleared_by_naming_a_profile, ‏tests/test_classification_policy.py::test_a_merged_confidence_reason_names_the_source_the_merge_can_see)` |
| **A7** | `tests/test_ai_tasks.py::test_a_quote_crossing_two_statements_is_checked_against_the_one_it_is_mostly_in (+ ::test_the_home_statement_is_the_one_the_quote_is_mostly_in_not_every_one_it_touches — הגארד נגד ההידוק)` |
| **A12** | `tests/test_ai_tasks.py::test_the_extraction_contract_carries_no_tag_field_for_a_gate_that_never_existed` |

### D3
זה נכון יותר לבדוק ברמת הפונקציה הטהורה מאשר טקסט משרה מלא, כי השאלה היא ישירות על
הנוסחה: `extraction_confidence(completeness=0.56, classified=1.0, understood_elsewhere=False)`
מול `classification_confidence(top=5, second=0)`.
**צפוי:** קריאה של 56% מהדרישות לא אמורה לעבור סף אישור של 0.72.
**בפועל:** `(0.4+0.6·0.56)·1.0 = 0.736`; `classification_confidence(5,0)=min(0.98,0.58+0.4)=0.98`;
`round(0.736·0.98,4)=0.7213 ≥ 0.72` → עובר, אפס approval reasons מ-confidence.
(תרחיש טקסט-משרה מלא לאותה נקודה: 9 בוליטים בסגנון D2 שבהם 5 ממופים ותואמים כ-matched —
דורש facts fixture קיים ב-`tests/test_analysis.py`, לא מצוטט כאן כדי לא להמציא fact IDs.)

### D7
לא ניתן לבטא כ-diff של קלט/פלט על טקסט משרה — זהו מדד שקבוע מתמטית תחת כל נתיב קוד קיים,
לא באג שמייצר ערך שגוי על קלט ספציפי. הטסט המתאים הוא assertion מבני: לכל
`ExtractedRequirement` שנוצר ע"י `extract_requirements` (כל קלט), `item.concept` הוא
תמיד מחרוזת לא ריקה (extraction.py:148-166 בונה אותו כך תמיד) → `concept_classification_
completeness(extracted)` שווה 1.0 עבור **כל** קלט לא-ריק. **צפוי מול בפועל:** אין הבדל —
זו הבעיה: אין שום קלט שמזיז את המדד הזה מ-1.0.

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

## Open product decisions

**RESOLVED:** #1-#15. **OPEN:** #16-#18 only — the three implementation forks #4's
split created, all in Stage 7. `A2`/`D7` are decided but wait on #18 and on two pieces
of structural work named under #15.

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

4. **RESOLVED — אין חוגה אחת. Stage 7 מתפצל לשלושה צירים, וכל אחד נשפט על הציר
   שלו.** ~~"כמה מחמיר ה-gate צריך להיות?"~~ — **השאלה עצמה הייתה המכשול.** היא
   מניחה שכל שבעת הממצאים יושבים על ציר אחד של "מחמיר מול מרשה", ובדיקה של כל
   אחד מהם בקוד מראה שלא. שלושה סוגים שונים, ושניים מהם לא שואלים שאלת מוצר בכלל:

   **ציר 1 — שער חלש ממה שהתיעוד שלו כבר מבטיח (`A5`, `A6`, `A7`, `A12`).
   מהדקים עד להבטחה, וזו אינה הכרעת מוצר.** הידוק כאן אינו יכול לדחות פלט
   תם-לב, כי הוא רק אוכף את מה שהחוזה כבר מצהיר:
   - `A5` — `demanded`/`kind` של הספק נכנסים ל-`threshold_coverage` בלי אימות
     מול הציטוט. אומת: `interpretation.py` לא מזכיר אף אחד מהשניים, בכל הקובץ.
     ספק תם שולח ערך שתואם את הציטוט שלו עצמו, ולכן אימות אינו דוחה אותו.
   - `A6` — ציטוט מ-`section == "other"` מותיר את שני התנאים `False`, ולכן
     הצהרת הספק אינה נבדקת כלל.
   - `A7` — ציטוט שחוצה גבול-statement מדלג בשקט, ו-`_same_statement` עונה על
     אותה שאלה ב-**חפיפה** בזמן שהלולאה ב-`verify_interpretation` עונה
     ב-**הכלה**. שתי הגדרות לשאלה אחת — באג, לא מדיניות.
   - `A12` — הדוקסטרינג מבטיח ש-tag זר פוסל הצעה; אף שורה לא קוראת את השדה.

   **ציר 2 — שער שסותר את הפרומפט של המערכת עצמה (`A8`, `A10`). מיישרים מול
   הפרומפט; זו אינה בחירת חומרה אלא תיקון סתירה.** שני אלה **דוחים פלט תקין
   היום**, ולכן דרישת הבדיקה האמפירית שהניסוח המקורי הציב חלה עליהם בעיקר —
   ושם **המצב הנוכחי כבר הוא מצב הכישלון**, כך שתיקון מסוכן פחות מהסטטוס-קוו,
   לא יותר:
   - `A8` — `system-v3.md:27-28` מורה לספק לצטט מרקר חובה ב-`context_quote`,
     ו-`_verify_context_quote_occurs` דוחה ציטוט שמופיע יותר מפעם אחת. **התיקון
     הזול הוא בפרומפט ולא בשער** — להורות לצטט את הביטוי המכיל את המרקר, ארוך
     מספיק כדי להיות יחיד — וזה משמר את מטרת השער האמיתית (מיקום חד-משמעי,
     שבלעדיו בדיקת same-statement עלולה לעבור מול המופע הלא-נכון).
   - `A10` — `matches[0] if len(matches) == 1 else None`, בזמן שהפרומפט מבקש
     לצטט את הדרישה כלשונה; בולט הנוגע בשני מושגים נופל תמיד ל-`undetermined`.

   **ציר 3 — רפיון ניקוד שאינו שער כלל (`A9`).** `"matched" if "matched" in
   member_coverages` הוא שאלה על סמנטיקת coverage של `any-of`, לא על חומרת
   שער, והוא נשפט עם `D8`/`C1` ולא עם השערים.

   **מה שנשאר פתוח אחרי הפיצול** הוא לא העמדה אלא שלוש הכרעות יישום שהפיצול
   *יוצר*, וכל אחת קטנה ומוגדרת: `A12` לממש-או-למחוק, `A7` לדחות-או-להכיל,
   ו-`A10` (היחיד שעדיין באמת דורש מדידה על מודעות אמת). נרשמו כהחלטות
   **#16-#18** למטה. **#13-#15 שמורות לשלוש שאלותיו של A2** כפי שהמסמך כבר
   ייעד אותן.

5. **RESOLVED — אותה נוסחה, אותה יחידה, על הפרופיל שנבחר בפועל.**
   `top = term_scores[profile]` ו-`second = max(term_scores[p] for p in ProfileName
   if p != profile)`, במקום `term_scores.most_common(2)`.

   **מה שפתח את המבוי הסתום:** הדוקסטרינג (classification.py:160-166) מציב אילוץ
   אמיתי — הסקאלה `0.58 + 0.08·top + 0.04·(top−second)` כוילה למספרי-מונחים
   קטנים, ו-"a coverage separation saturates it: 12 against 9 would report
   near-certainty for a two-fact margin". האילוץ הזה אוסר להזין לנוסחה **יחידה**
   אחרת. הוא **אינו** אוסר להזין לה את אותה יחידה על **נושא** אחר, וזה בדיוק מה
   שנעשה כאן. ההסתייגות המתועדת נשמרת במלואה; לא נוצרת סקאלה שנייה לכייל.

   **שלושת המקרים:**
   - coverage הכריע והווקבולרי מסכים → `top` הוא של הנבחר → **ציון זהה להיום**,
     אפס רגרסיה.
   - coverage הכריע והווקבולרי חולק → `top − second` שלילי → `max(0, ...)` מאפס
     את בונוס-המרווח והציון יורד לבסיס. זה התיקון: בתרחיש של D8 הווקבולרי דוחף
     ל-DEVELOPMENT בזמן שה-coverage בחר ACCOUNT_MANAGER, והמערכת מדווחת היום
     `0.9+` על סמך מונחים שהצביעו **נגד** ההחלטה.
   - coverage שוויוני והווקבולרי הכריע → הנבחר *הוא* המוביל → ללא שינוי.

   **המשמעות של המספר משתנה, וזו הנקודה:** מ-"כמה הפריד הווקבולרי" ל-"כמה
   הווקבולרי תומך בהחלטה שהתקבלה". השנייה היא טענה נכונה על ההחלטה שנשמרה;
   הראשונה הייתה טענה נכונה על משהו שלא הכריע.

   **שתי נגזרות שנרשמו ולא נבלעו:**
   - `ambiguous-signals` נדלק על **תיקו** בדירוג. **מחלוקת** בין coverage
     לווקבולרי אינה תיקו, ואף reason לא מדווח עליה — ר' פריט מעקב 17.
   - `profile_override` סותר-ווקבולרי יוריד עכשיו את הציון ועלול להדליק
     `low-confidence` על בחירה מפורשת של המשתמש. זה משיק ישירות ל-C1
     (החלטה #6) ונשקל שם, לא כאן. אומת שהסדר מאפשר זאת: `profile` סופי (כולל
     override) לפני שהקלטים ל-confidence מחושבים.

6. **RESOLVED — שני reason-codes, והגבול ביניהם הוא "האם ה-override בכלל יכול
   לנקות את זה".**
   - `"low-confidence-extraction"` → `frozenset({"analysis"})`, `ANALYSIS_INCOMPLETE`
   - `"low-confidence-classification"` → `frozenset({"track","profile"})`,
     `CLASSIFICATION_AMBIGUITY`

   **ההנמקה כבר כתובה בקוד, שתי שורות מעל הרשומה הפגומה.** approval.py:65-67,
   על `extraction-failed`: *"Naming the Track or Profile does not recover a
   requirement that was never read, so those do not answer this one."* זה תקף
   מילה-במילה ל-`low-confidence` שמקורו ב-extraction, והוא פשוט לא הורחב לשם.
   הטבלה כבר מחזיקה את התבנית הנכונה (`{track,profile}`/`CLASSIFICATION_AMBIGUITY`
   מול `{analysis}`/`ANALYSIS_INCOMPLETE`); C1 הוא ההפרדה הזו שלא הגיעה לשורה
   אחת.

   **הגבול נגזר מהנוסחה, לא מקבוע חדש.** `classification_confidence` חסום
   ב-`min(0.98, ...)`, ולכן:

   ```
   extraction_score < CONFIDENCE_APPROVAL_THRESHOLD / 0.98 ≈ 0.735
      ⇒ שום ערך של classification לא יחצה את הסף ⇒ ה-extraction הוא החוסם
   ```

   זו בדיוק השאלה שמעניינת — לא "איזה גורם נמוך יותר" (שרירותי בשוליים) אלא
   "האם בחירת Profile בכלל **יכולה** לפתוח את השער". ה-override שעונה על reason
   הוא ה-override שיכול באמת לנקות אותו. **התקרה `0.98` צריכה לעלות לקבוע
   בעל-שם** כשזה מיושם, כי היא הופכת מפרט-מימוש לחלק מהגדרת הגבול.

   **רשומות היסטוריות: `"low-confidence"` נשאר רשום בטבלה בדיוק כפי שהוא**
   (`{track,profile}`/`CLASSIFICATION_AMBIGUITY`). ניתוחים שכבר נכתבו נושאים את
   הקוד הזה, והחלטה #8 אוסרת לגעת בהם; הידוק שלו ל-`{analysis}` היה חוסם
   רטרואקטיבית ניתוחים שהיו ניתנים לאישור. שני הקודים החדשים הם לניתוחים חדשים
   בלבד. **הגארד הנגזר** ("every reason the engine records is registered") יתפוס
   את שניהם אם יישכחו.

   **מקור שלישי שהתגלה בקוד ולא היה במסמך — `merge_classification`.** יש **שני**
   אתרי פליטה ל-`low-confidence`, לא אחד: `classify_job` (classification.py:573)
   ו-`merge_classification` (approval.py:196-197). השני מחשב
   `confidence = min(deterministic.confidence, proposal.confidence)` — מכפלה של
   מכפלות — **ואין לו גישה לשני הגורמים כלל**, ולכן אינו יכול לפצל.

   זה לא פגם בהכרעה אלא מקרה שלישי שהיא לא צפתה, ויש לו תשובה טובה: כש-`min`
   מגיע מה-**proposal**, המקור אינו extraction ואינו classification של הצינור
   שלנו — זו אי-ודאות שהספק הצהיר על עצמו. **הקוד הערום `"low-confidence"` נשאר
   בדיוק בשביל זה**, ומשרת שני תפקידים לגיטימיים: רשומות היסטוריות, והמקרה
   הזה. `{track,profile}` הוא ה-override הנכון עבורו — ספק שלא היה בטוח בסיווג
   נענה בבחירת Profile. **שים לב:** `merge_classification` כבר יורש
   `reasons = list(deterministic.approval_reasons)`, ולכן הקוד המפוצל
   מ-`classify_job` זורם דרכו מעצמו; אין צורך לשכפל את הלוגיקה שם.

   **אינטראקציה עם החלטה #5, שנבדקה ואינה יוצרת קיפאון:** אחרי #5,
   `profile_override` שסותר את הווקבולרי מוריד את `classification_score` ועלול
   להדליק `low-confidence`. הוא יהיה מסוג **classification**, וה-override שגרם
   לו *הוא* ה-override שעונה עליו — המשתמש בחר, הציון מדווח ביושר תמיכה
   ווקבולרית נמוכה יותר, והשער נפתח באותה בקשה.

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
    **עודכן ב-Stage 6: נשקל מחדש אחרי ש-D9 תוקן, וההכרעה נשארה `mandatory=False`.**
    הנימוק שלהלן — "‏`section` שגוי כי D9 לא תוקן" — פג, והוחלף בנימוק שאינו
    תלוי באמינות `section`: הישות קיימת בדיוק כי שום דבר לא קרא מה השורה
    מבקשת, ו-`mandatory=True` היה טוען חובה על טקסט שהדרישה שבו לא זוהתה.
    ר' "מה נחת ב-Stage 6" בראש המסמך ואת הדוקסטרינג של `undetermined_requirement`.
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
    שלא-תוקן, בלי לאבד הגנה בפועל. ~~לשקול מחדש ל-mandatory מ-section אחרי ש-D9
    מתוקן (Stage 6)~~ — **נשקל ב-Stage 6, והתשובה נשארה `mandatory=False`.**

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

13. **RESOLVED — אין גורם `classified` בנתיב ה-AI. ציטוט מאומת שאף קונספט לא
    הצליח לסווג אינו נספר כ"נקרא", ומחויב ל-completeness — בדיוק כמו בנתיב
    הדטרמיניסטי.**

    **האסימטריה שלא נוסחה עד כה, והיא הממצא האמיתי:** בנתיב הדטרמיניסטי שורה
    שאי אפשר לסווג **אינה הופכת** ל-`ExtractedRequirement` כלל, ולכן נופלת
    ב-`completeness`. בנתיב ה-AI אותה שורה הופכת ל-`Requirement(concept=None)`
    **ונכנסת ל-`mapped_spans`**, כלומר נספרת כ*נקראה* ב-`by_ai` — ואף מדד לא
    מחייב אותה. זה החור; לא היעדרו של גורם, אלא זקיפת קרדיט על מה שלא הובן.

    **ולכן התשובה אינה "להוסיף גורם" אלא לסגור את החור במקום שנפער.** ‏`D7`
    מוכיח ש-`concept_classification_completeness` קבוע `1.0` בנתיב הדטרמיניסטי
    **מבנית ולא במקרה** — אי אפשר לחלץ שם בלי לסווג. בניית אנלוג חי בנתיב ה-AI
    הייתה הופכת את שתי המכפלות ללא-ברות-השוואה, וזה ההפך ממה ש-`confidence`
    מאוחסן בודד אמור לאפשר.

    **מה שזה עושה לשתי השאלות האחרות — הן מתמוססות, ולכן נסגרות איתה:**

14. **RESOLVED (נגזרת מ-#13) — ישויות `undetermined` סינתטיות: מחוץ למונה,
    בתוך המכנה.** השאלה הייתה חיה רק אם #13 נענית בחיוב. משאין גורם `classified`,
    אין עונש כפול שצריך למנוע, ו-`by_ai / len(requirement_lines)` נשאר בדיוק
    צורת הנתיב הדטרמיניסטי — מה שכבר מתקיים היום.

15. **RESOLVED (נגזרת מ-#13) — רצפת ה-0.4 של `understood_elsewhere` חלה, באותו
    אופן.** משזו אותה נוסחה על אותה יחידה, אין שאלה נפרדת: `bool(rule_gaps)`
    מועבר פנימה כמו בנתיב הדטרמיניסטי.

    **‏`D7` משתחרר עם #13:** הגורם קבוע `1.0` בנתיב היחיד שיש לו אותו, ולא נוצר
    שני. אפשר להסירו — אבל **רק יחד עם A2**, כי עד אז הוא עדיין הגורם `classified`
    של הנוסחה החיה.

    **שני תנאים מוקדמים שנשארים ל-A2, ואינם הכרעות מוצר אלא עבודה:**
    - **‏#18 חייבת להיפתר קודם.** `concept_for_quote` מחזיר `None` גם כששני
      קונספטים תואמים (`A10`), כלומר הציטוט שהפרומפט עצמו מבקש ייזקף כלא-נקרא.
      בנייה על המדידה הזו לפני שהיא תוקנה היא בנייה על מדידה שבורה.
    - **‏`mapped_spans` משרת היום שני תפקידים** — "מה נקרא" (למדידה) ו"מה לא
      דורש splice סינתטי" (‏A11 דרש זאת מפורשות). ההכרעה מפרידה ביניהם, וזה
      מבנה חדש ולא שורה.
    - **החסם המבני נשאר בכל תרחיש:** מאוחסנת רק המכפלה, ו-
      `deterministic_confidence`/`proposal_confidence` מפצלים deterministic מול
      ספק, לא extraction מול classification. נדרש פרמטר מפורש חדש או שדה מאוחסן
      חדש.

16. **RESOLVED — למחוק את ההבטחה ואת השדה.** ‏`topic_tags` ירד מ-
    `ProposedRequirement`, ושתי ההצהרות השקריות נמחקו והוחלפו בהסבר במקומן.
    **מה שהכריע, ונמצא בקוד ולא במסמך:** (א) ההצהרה השנייה
    (`ai_extraction.py:11`) נקבה בצרכן — "consulted only as a boundary-
    association hint elsewhere (`coverage.py`)" — ו-`coverage.py` לא מזכיר
    את השדה כלל, כלומר היו **שתי** הבטחות שקריות ולא אחת; (ב) `_strict_schema`
    (`providers.py:241`) "rewrites `required` and closes every object", ולכן
    השדה היה **חובה** בסכמה שנשלחה — כל ספק חויב לפלוט תגיות שאיש לא קורא;
    (ג) הפרומפט (`system-v3.md`) לא מזכיר תגיות בכלל, ולכן הספק מעולם לא
    הונחה מה לשלוח; (ד) **אין בשום מקום ווקבולר תגיות מוצהר**, ולכן "tag זר"
    לא היה ניתן להגדרה — מימוש השער היה מחייב להמציא ווקבולר חדש, לא לכתוב
    בדיקה. **מחיר שנלקח במודע:** סכמת הפלט השתנתה, ולכן
    `output_schema_version` של `propose_requirement_extraction` עלה
    `"1.0.0"→"2.0.0"` (חמשת שאר ה-tasks כבר ב-2.0.0). ‏`extra="forbid"` אומר
    שספק שימשיך לשלוח `topic_tags` ייכשל ב-`INVALID_OUTPUT` — זה מכוון: השדה
    לא יכול לחזור כנתון לפני שהוא חוזר כהחלטה. **נסגר גם פריט מעקב 7**:
    ‏`ProposedRequirement.label` תועד במפורש כלא-נקרא-בכוונה, באותו דוקסטרינג.
    **השאלה שנשאלה** (מפיצול #4, ציר 1): לממש את השער שהדוקסטרינג מבטיח, או
    למחוק את ההבטחה — כשמה שאסור הוא להשאיר את הפער, שגרוע מקוד מת מפני
    שקורא הקובץ מאמין שיש הגנה שאין.

17. **RESOLVED — סטייטמנט-בית לפי חפיפה מרבית, והגדרה אחת לשתי השאלות.**
    ‏`_overlap` הוא עכשיו הפרימיטיב היחיד; `_home_statement` בוחר את
    הסטייטמנט שהספן חופף לו הכי הרבה (תיקו → המוקדם), ו-`_same_statement`
    נשאר "כל סטייטמנט משותף" אבל נשען על אותו פרימיטיב. **למה לא דחייה:**
    הפרומפט אומר "quote the exact source text verbatim" ואינו מבטיח שדרישה
    יושבת בסטייטמנט אחד — ולכן דחיית ספן חוצה אינה "הידוק עד להבטחה" (ציר 1)
    אלא כלל חדש שהספק לא הוזהר עליו (ציר 2, שדורש מדידה). **למה לא כל
    סטייטמנט חופף:** ספן שנכנס כמה תווים לבולט "preferred" שכן היה חוסם
    פרשנות `mandatory` שהבולט של הדרישה עצמה תומך בה — הידוק, בזמן שפריט
    מעקב 15 קובע שכיוון התיקון בנתיב ה-AI הוא הרפיה. **מה שהשתנה בפועל:**
    הבדיקה **רצה** עכשיו על ספן חוצה, במקום ליפול מהלולאה בלי לבדוק דבר.
    **השאלה שנשאלה** (מפיצול #4, ציר 1): הדילוג השקט ושתי ההגדרות היו באג
    לסגירה בכל מקרה; מה שהיה פתוח הוא רק לאן ליישר — לדחות ספן שאינו מוכל
    בסטייטמנט יחיד, או לשאול בחפיפה ולבדוק ממילא.

18. **OPEN — `A10`: ציטוט שתואם שני קונספטים — מה הוא צריך להחזיר?**
    נוצרה מפיצול החלטה #4 (ציר 2), ו**זו היחידה מהשלוש שעדיין באמת דורשת מדידה
    על מודעות אמת.** `matches[0] if len(matches) == 1 else None` נופל תמיד על
    בולט שנוגע בשני מושגים — בדיוק מה שהפרומפט מבקש לצטט. הדוקסטרינג מנמק את
    ה-`None` ("silently picking the first match would misclassify coverage as
    confidently as picking none"), וזה נכון; מה שלא נשקל הוא ששתי האפשרויות
    האלה אינן היחידות. **מה שההכרעה תלויה בו:** כמה שכיח בפועל ציטוט
    רב-קונספטי, ומה שיעור ה-`undetermined` שהוא מייצר היום.
