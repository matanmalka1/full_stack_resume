# א. Executive Summary

מצב כללי: טוב מאוד. זה codebase ממושמע בצורה חריגה. גבולות השכבות ב-backend נאכפים ע"י בדיקה נגזרת (tests/test_architecture.py) עם ARCHITECTURE_DEBT_ALLOWLIST ריק — אפס דליפות. אין barrel files, אין מעגלי import, אין console.* ב-frontend, כל except Exception ב-backend הוא cleanup-then-raise ששומר context. הרוב המכריע של המפות (labels/tones) ממופתח על ה-unions המיוצרים מ-OpenAPI, כך שתוספת state בשרת שוברת build במקום להגיע למסך בלי תרגום.

שלושת מוקדי הסיכון:

- כפילות intake מלאה — QuickIntakeDialog.tsx הוא העתק כמעט מילולי של הלוגיקה ב-NewApplicationPage.tsx: ~120 שורות של mutation, מפתח idempotency, טיפול בכפילויות ובתשובה מיושנת. צד אחד מכוסה בטסטים, השני לא בכלל.
- שלושה קיבוצים סותרים של שלבי גיוס — סרגל הפילטר, לוח ה-pipeline וה-preset בשרת מקבצים את אותם statuses אחרת. זו אי-עקביות גלויה למשתמש, לא רק חוב.
- מפתחות idempotency דרך useMemo(() => crypto.randomUUID(), [deps]) בארבעה מקומות. React לא מתחייב לשמר useMemo; אובדן cache מייצר מפתח חדש ושובר בדיוק את החוזה של §13 שהקוד מתאר בהערות. באותו codebase כבר קיים דפוס דטרמיניסטי בטוח יותר.

אזורים שעובדים היטב — לא לגעת:

- שכבת ה-API של ה-frontend (frontend/src/api/) — טיפוסים נגזרים, query keys סדורים, queuedOperation כבדיקת חוזה §13 יחידה.
- useDraftAutosave.ts — serialization, restore, conflict; מהודק ומכוסה.
- applicationActionPlan.ts — קריאת הפרויקציה מופרדת מהציור ונבדקת בלי DOM. זה המודל שכדאי לחזור עליו.
- WorkflowLandmark.tsx, applicationListParams.ts — טבלאות ממצות נגזרות.
- אכיפת הגבולות ב-backend.

היקף: בינוני. ~13k שורות frontend לא-טסט. אין צורך ב-rewrite. רוב הממצאים הם 4 חילוצים ממוקדים + 5 איחודי אוצר-מילים.

## ב. Findings לפי עדיפות

| ID | Sev | Conf | Category | Location | Problem | Recommended change |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | High | High | כפילות | ✅ בוצע — QuickIntakeDialog.tsx:23-147 ↔ NewApplicationPage.tsx:37-241 | ~120 שורות intake מועתקות | חילוץ useApplicationIntake |
| F2 | High | High | כפילות + באג | ✅ בוצע — PipelineStagesBar.tsx:7-37 ↔ ApplicationAlternativeViews.tsx:167-188 | קיבוצי שלבים סותרים | מודול recruitmentStages.ts יחיד |
| F3 | High | Medium | correctness | ✅ בוצע — useApplicationActionsMutations.ts:36,39,116, OperationActions.tsx:31 | useMemo+UUID כזהות יציבה | מפתח נגזר דטרמיניסטי |
| F4 | High | High | גבול שכבות | applicationListPresentation.ts:106 ↔ queries.py:327 | חוק עסקי בשני runtime | שדה בפרויקציה |
| F5 | Medium | High | state/כפילות | ✅ בוצע — useDraftEditorState.ts:31, AutomaticDraftNotice.tsx:19, useApplicationActionsMutations.ts:29 | enabled:false × 3 + הבהוב | hook useSettings() |
| F6 | Medium | High | כפילות | ✅ בוצע — FactLifecyclePanel.tsx:41-47 ↔ CanonicalFactsBrowser.tsx:14-30,69 | אוצר מילים לעובדות פעמיים, סותר | factLabels.ts |
| F7 | Medium | High | כפילות + סמנטיקה | ✅ בוצע — UrgentActionHub.tsx:31-63 ↔ applicationListPresentation.ts:14-27 | שני חישובי "באיחור" שונים | פונקציה אחת |
| F8 | Medium | High | כפילות | ✅ בוצע — useRevisionPageState.ts:95-106 | גזירה מחדש של warnings מהשרת | להשתמש ב-warningTitle |
| F9 | Medium | Medium | data loss | ✅ בוצע — useDraftAutosave.ts:218-225 | unmount מוחק עריכה תלויה | flush ב-unmount |
| F10 | Medium | High | SoC | ✅ בוצע — FactLifecyclePanel.tsx (334) | 10 useState, לא useAppForm | פיצול + טופס |
| F11 | Medium | High | חילוץ | ✅ בוצע — DraftEditorPage.tsx:103-264 | 2 בלוקי JSX גדולים inline | 2 קומפוננטות |
| F12 | Medium | High | efficiency | ApplicationListPage.tsx:99-121 | 10 שאילתות רשימה לרינדור | endpoint counts |
| F13 | Medium | Medium | SoC | queries.py (895) | DTOs + narrowing + mappers | פיצול לחבילה |
| F14 | Low | High | Loading | ✅ בוצע — ArtifactsPanel.tsx:205, CanonicalFactsBrowser.tsx:53-66 | מסך ריק / סולם ידני | QueryState |
| F15 | Low | High | כפילות | ✅ בוצע — ApplicationListPage.tsx:255-277 ↔ ViewSwitch.tsx | switch inline למרות primitive | להשתמש ב-ViewSwitch |
| F16 | Low | High | כפילות | ✅ בוצע — applicationListPresentation.ts:5-10 | פורמטר תאריך רביעי | style: "date" |
| F17 | Low | High | כפילות | ✅ בוצע — 8 אתרי invalidateQueries | תבנית חוזרת לא-עקבית | invalidateApplicationViews |
| F18 | Low | High | error handling | NewApplicationPage.tsx:155, QuickIntakeDialog.tsx:99 | סיבת כשל הניתוח נזרקת | לשמר ProblemDetails |
| F19 | Low | Medium | validation | RecruitmentExceptionalActions.tsx:78 | toISOString() בלי הגנה | להוסיף בדיקה |
| F20 | Low | High | גבול | useWatchedOperation.tsx:7,81 | hooks/ תלוי ב-pages/ | להחזיר נתונים, לא JSX |
| F21 | Low | High | כפילות | 3 מסכים × throw new Error("... rendered without ...") | הגנת param משולשת | useRequiredParam |

## הרחבה על הממצאים המשמעותיים

### F1 — כפילות intake מלאה High / High ✅ בוצע

התנהגות קיימת. שני משטחים יוצרים מועמדות. NewApplicationPage.tsx (מסך) ו-QuickIntakeDialog.tsx (דיאלוג בלוח). זהים ממש, לא "דומים":

| פריט | NewApplicationPage | QuickIntakeDialog |
| --- | --- | --- |
| LABEL_MAX_CHARACTERS / SOURCE_URL_MAX_CHARACTERS | :37-38 | :23-24 |
| NewApplicationFields/QuickIntakeFields + emptyFields | :45-57 | :27-39 |
| intakeFrom | :79-89 | :41-50 |
| SubmitInput / SubmitResult | :91-95 | :52-59 |
| mutationFn (dup-check → create → settings → startAnalysis, מפתח create:${appId}:${snapshotId}, catch בולע) | :118-160 | :79-102 |
| submitStateRef + שני effects | :177-193 | :110-126 |
| runSubmit | :212-224 | :135-139 |
| בלוק answeredIntake…failure (6 שורות) | :229-236 | :141-147 |
| withinBudget | :359-363 | :231-232 |

עלות תחזוקה. כל שינוי במדיניות הקליטה — פורמט מפתח ה-idempotency, קונטרקט הכפילויות, טיפול בתשובה מיושנת — חייב להיעשות פעמיים. NewApplicationPage.test.tsx (461 שורות) מגן על אחד מהם בלבד; לדיאלוג אין טסט כלל. כלומר הדריפט כבר לא נתפס.

זו לא abstraction מוקדמת. האחריות זהה (מדיניות קליטה), הסיבה לשינוי זהה (חוזה השרת). מה ששונה לגיטימית הוא רק ה-JSX: מסך מלא עם מונה בייטים, העלאת קובץ ו-PageShell מול דיאלוג קומפקטי.

המלצה מצומצמת. frontend/src/pages/new-application/useApplicationIntake.ts:


```ts
useApplicationIntake({ onCreated }) → {
  form,            // UseFormReturn<ApplicationIntakeFields>
  submit,          // UseMutationResult
  runSubmit,       // (acknowledged?) => submit handler
  duplicates,      // DuplicateMatch[] | null
  staleAnswer,     // boolean
  failure,         // unknown | null
  answeredIntake,
}
```

הקבועים, emptyFields, intakeFrom, ה-mutation ובלוק הגזירה עוברים לתוכו. שני המשטחים שומרים JSX משלהם.

Trade-offs. hook עם 7 יציאות; מוצדק כי כולן קשורות ל-mutation אחד. רגרסיה בעיקר במסך המכוסה — הדיאלוג ייחשף רק ידנית או ב-e2e. Refactor בלבד, ללא שינוי התנהגות. מוגן ע"י NewApplicationPage.test.tsx ו-e2e/new-application.spec.ts.

### F2 — שלושה קיבוצי שלבי גיוס סותרים High / High ✅ בוצע (assignment→interviews, final_stage→offer, לפי הכרעת המשתמש)

התנהגות קיימת.

PipelineStagesBar.tsx:7-37 (סרגל הפילטר):


```text
screening  = [recruiter_screen]
interviews = [interview, assignment]
offer      = [final_stage, offer, accepted]
```

ApplicationAlternativeViews.tsx:167-188 (לוח ה-pipeline):


```text
screening  = [recruiter_screen, assignment]
interviews = [interview, final_stage, offer, accepted]
closed     = [rejected, withdrawn, closed]
```

queries.py:246-256 — _INTERVIEW_STATUSES (ה-preset active_interviews): recruiter_screen … offer.

הסיכון — גלוי למשתמש. המשתמש לוחץ "ראיונות ומטלות" בסרגל (מסנן interview+assignment), עובר לתצוגת pipeline, ומוצא שהשתיים יושבות בעמודות שונות. final_stage/offer/accepted הפוכים באותה מידה. שני הקבצים גם משכפלים מילולית את אוצר ה-tone "neutral"|"accent"|"warning"|"success" ואת מפת ה-classes שלו (PipelineStagesBar.tsx:41-62 מול ApplicationAlternativeViews.tsx:190-195) — וזה tone נפרד מ-StatusTone של ui/status.ts, שלישי במניין.

זו כפילות אמיתית. שני המקומות עונים על אותה שאלה: "לאיזה שלב שייך status". ההבדל הלגיטימי היחיד הוא שהלוח מציג גם עמודת סגורים.

המלצה. frontend/src/pages/application-list/recruitmentStages.ts שמייצא recruitmentStages (id, label, statuses, icon, tone) + closedStage + selectedStage(), ממצה על RecruitmentStatus כמו שאר המפות בקוד. הסרגל צורך את הפעילים; הלוח את הפעילים + סגורים. את pipelineToneClasses להשאיר לכל צרכן (הן באמת ויזואליות שונות) אבל את ה-union לייצא מהמודול.

Trade-offs. צריך החלטה מוצרית אחת: לאיזה שלב שייך assignment ולאיזה final_stage. זו הכרעה של המשתמש — לא אאחד בשקט. אין טסט על אף אחד מהשניים; כדאי טסט קטן על selectedStage. דורש שינוי התנהגותי (הקיבוץ בצד אחד ישתנה).

### F3 — מפתחות idempotency דרך useMemo High / Medium ✅ בוצע

התנהגות קיימת. ארבעה מפתחות נבנים כך:


```ts
const analyzeKey = useMemo(() => crypto.randomUUID(), [snapshotId]);   // :36
const draftKey   = useMemo(() => crypto.randomUUID(), [...]);          // :39
const replaceKey = useMemo(() => crypto.randomUUID(), [staleDraftId, editVersion]); // :116
const retryKey   = useMemo(() => crypto.randomUUID(), [operation.id]); // OperationActions:31
```

ההערות מתארות סמנטיקה נגזרת ("one key per snapshot", "one key per replaced version"). אבל הערך אינו נגזר מהמערך — המערך משמש כ-cache key בלבד.

הסיכון. React מגדיר useMemo כאופטימיזציה, לא כערובה סמנטית; הוא רשאי להשליך את ה-cache. אם זה קורה, לחיצה חוזרת שולחת Idempotency-Key חדש לאותה פקודה, והשרת רואה פקודה חדשה — כלומר Operation שני. עבור analyze זה ניתוח כפול; עבור replace_working_draft זו החלפה שנייה של אותה טיוטה. זה בדיוק החוזה ש-operations.ts:65-81 קיים כדי לשמור.

התיקון כבר קיים בקוד. ארבעה מפתחות אחרים באותו codebase כן דטרמיניסטיים:

- DraftRenderPanel.tsx:33 — render:${approvedRevisionId}
- NewApplicationPage.tsx:145 — create:${appId}:${snapshotId}
- useRevisionPageState.ts:43-47 — revision-draft:${...}
- useDraftEditorState.ts:207 — ${draft.id}:${version}:${target}

המלצה. להמיר את הארבעה לאותו דפוס: analyze:${appId}:${snapshotId}, draft:${analysisId}:${planId}, replace:${draftId}:${editVersion}, retry:${operationId}.

Trade-offs. מפתח דטרמיניסטי אומר שניסיון חוזר אחרי כשל קבוע יחזיר את אותה תשובה שמורה במקום להריץ מחדש. במקרה של retry זה דווקא הכוונה. יש לוודא מול docs/spec/state-and-use-cases.md §13 את חלון השמירה של מפתחות. דורש בדיקה מול הספק — אם הספק אומר שהמפתח חייב להתחלף בין ניסיונות, אז הפתרון הוא useRef + מפתח מסומן, לא useMemo. מוגן ע"י StaleDraftCommands.test.tsx.

### F4 — חוק "מועמדות סגורה" חי בשני runtime High / High

התנהגות קיימת.

cv_engine/application/queries.py:327-332:


```python
CLOSED_RECRUITMENT_STATUSES = frozenset({"rejected", "withdrawn", "closed"})
def _is_closed(item): return item.terminal_outcome is not None or item.recruitment_status in CLOSED_RECRUITMENT_STATUSES
```

applicationListPresentation.ts:106-109:


```ts
const closedStatuses = new Set(["rejected", "withdrawn", "closed"]);
export const isApplicationClosed = (item) => item.terminal_outcome != null || closedStatuses.has(item.recruitment_status);
```

זהה שורה-לשורה. ההערה בקוד ה-frontend כבר מודה בזה: "A future can_close projection should replace this duplicated client-side classification." משמש ב-3 מקומות (UrgentActionHub.tsx:52, ApplicationAlternativeViews.tsx:35, ApplicationListRow.tsx:102,171).

זו סתירה מול AGENTS.md, לא רק כפילות: "React is the product interface... Logic belongs to the application layer." וגם התיעוד ב-contracts.ts:17-19 אומר במפורש שהלקוח לא נגזר מחדש מצב. אין guard נגזר שיתפוס דריפט — סטטוס סופני חדש בדומיין יעבור את ה-build של שני הצדדים ויסווג נכון רק באחד.

המלצה. להוסיף שדה בוליאני לפרויקציה (is_closed על ApplicationListItemView), לחשוף דרך OpenAPI, ולמחוק את isApplicationClosed.

⚠️ זה שינוי בשדה פרויקציה — לפי AGENTS.md הוא גורר את הבדיקה הדטרמיניסטית מקצה-לקצה (tests/test_pipeline_end_to_end.py) מול PostgreSQL נקי, בנוסף ל-tests/test_application_list_query.py ולרגנרציה של openapi/types.ts. דורש שינוי התנהגותי בחוזה. אם העלות לא מוצדקת עכשיו — הפתרון הזול הוא לפחות לקבע את הסט בטסט משותף, אבל זה guard ידני ולכן פחות טוב מהנגזר.

### F5 — קריאת Settings בשלושה עותקים עם enabled: false Medium / High ✅ בוצע

התנהגות קיימת. App.tsx:33 מבצע את הקריאה האמיתית. שלושה צרכנים קוראים מה-cache:


```ts
useQuery({ ...settingsQueryOptions, enabled: false })
```

ב-useDraftEditorState.ts:31, AutomaticDraftNotice.tsx:19, useApplicationActionsMutations.ts:29.

המחיר.

- התלות ב-App לא מוצהרת בשום מקום — enabled:false אומר "אל תביא", לא "מישהו אחר כבר הביא". שלושה עותקים של הנחה סמויה.
- הבהוב אמיתי: ברינדור הראשון קריאת App עדיין pending, ולכן regenerationAvailable הוא false (useDraftEditorState.ts:32). העורך מרנדר את ה-callout "יצירה מחדש באמצעות AI אינה זמינה" (DraftEditorPage.tsx:266-275) וכפתורי היצירה מחדש כבויים — גם כשה-AI כן מוגדר — עד שהקריאה חוזרת.
- settingsQuery.error ב-useApplicationActionsMutations.ts:209 הוא ענף מת: query שאינו רץ אינו נכשל.

המלצה. frontend/src/api/useSettings.ts:


```ts
useSettings() → { settings: Settings | undefined, isPending: boolean }
```

עוטף את הדפוס פעם אחת ומשמיע את המצב "עוד לא ידוע". הצרכנים מבדילים בין "AI לא זמין" ל-"עוד לא יודעים": ה-callout ב-DraftEditorPage מוצג רק כש-!isPending. זה כן semantic boundary — לא wrapper ריק.

Trade-offs. שינוי התנהגותי קטן וחיובי (ה-callout מפסיק להבהב). מוגן ע"י DraftEditorPage.test.tsx.

### F6 — אוצר מילים לעובדות פעמיים, וסותר Medium / High ✅ בוצע

FactLifecyclePanel.tsx:41-45: pending: "ממתינה"
CanonicalFactsBrowser.tsx:14-18: pending: "ממתינה לאישור"

אותה עובדה מוצגת בשני שמות בשני מסכים. בנוסף, כלל התצוגה renderings.he ?? renderings.en ?? meaning כתוב פעמיים — FactLifecyclePanel.tsx:47 כפונקציה, CanonicalFactsBrowser.tsx:69 inline.

זו כפילות מקרית שכדאי להסיר, ויש לה מקום מוכן: לכל דומיין אחר יש מודול labels — applicationLabels.ts, analysisLabels.ts, artifactLabels.ts, operationLabels.ts, draftLabels.ts. עובדות הן הדומיין היחיד בלי אחד.

המלצה. frontend/src/pages/facts/factLabels.ts עם factStatusLabels/factStatusTones/factStatusIcons (ממצים על FactStatus) ו-factLabel(fact). Refactor + החלטת נוסח אחת (איזו מהשתיים נשארת). ללא כיסוי טסטים כרגע.

### F7 — שני חישובי "באיחור" שנותנים תשובות שונות Medium / High ✅ בוצע

applicationListPresentation.ts:14-27 — isNextActionOverdue: new Date(value) מול חצות מקומי.
UrgentActionHub.tsx:31-63 — localDateKey + isDateOnly + השוואת מחרוזות.

הבדלים ממשיים:

- new Date("2026-09-01") נפרס כחצות UTC; localDateKey בונה תאריך מקומי. למשתמש שאינו ב-UTC השניים יכולים לחלוק על יום שלם — השורה בטבלה תגיד "באיחור" בעוד הכרטיס במוקד הפעולות לא יופיע (או להפך).
- hubItems מדלג בשקט על תאריך שאינו YYYY-MM-DD (:60); isNextActionOverdue מתייחס אליו כתאריך.

המלצה. להשאיר את isNextActionOverdue כבעלים היחיד, להוסיף לו isDueToday, ולמחוק localDateKey/isDateOnly מהמוקד. דורש הכרעה על אזור הזמן הקנוני — זו תזכורת שהמשתמש קבע, ולכן "מקומי" הוא ככל הנראה התשובה, כלומר isNextActionOverdue צריך לפרוס ${value}T00:00:00 ולא UTC. אין טסטים על אף אחד מהשניים; זה מקום שמצדיק כיסוי חדש.

### F8 — הגזירה של "גרסה מוכנה ישנה" בשלושה עותקים Medium / High ✅ בוצע

useRevisionPageState.ts:95-102 משווה job_snapshot_id/job_analysis_id ומרכיב משפט עברי משלו. שתי השורות אחריו (:103-106) מסננות החוצה את READY_REVISION_FOR_OLDER_SNAPSHOT ו-READY_REVISION_FOR_OLDER_ANALYSIS — בדיוק את שתי האזהרות שהשרת כבר שלח על אותה מסקנה. ול-applicationLabels.ts:190-195 כבר יש כותרות עבריות לשני הקודים האלה.

כלומר: אותו חוק מיוצג שלוש פעמים — בשרת, בגזירה המקומית, ובמפת הכותרות.

המלצה. למחוק את historicalContext ואת המסנן, ולרנדר את כל האזהרות דרך warningTitle. אם הנוסח הארוך חשוב, להעביר אותו למפה כטקסט גוף לצד הכותרת. Refactor, מקטין קוד. מוגן חלקית ע"י StageEPages.test.tsx.

### F9 — autosave מאבד עריכה בזמן ה-debounce Medium / Medium ✅ בוצע

useDraftAutosave.ts:218-225:


```ts
useEffect(() => () => { if (timer.current !== null) clearTimeout(timer.current); }, []);
```

ה-cleanup מנקה את הטיימר בלי send(). תרחיש: המשתמש מקליד בטענה, ותוך פחות מ-700ms לוחץ "חזרה להכנת קורות החיים" (DraftEditorPage.tsx:307). ה-buffer מת עם הקומפוננטה. onBlur={autosave.flush} (:184) מכסה את רוב המקרים אבל לא ניווט מקלדת/כפתור שאינו מייצר blur לפני unmount.

זה מתנגש עם הכוונה המוצהרת של הקובץ: "the local text is preserved and offered as an explicit choice, never dropped."

המלצה. לקרוא send() ב-cleanup לפני ניקוי הטיימר, או להשתמש ב-beforeunload+unmount flush.

Trade-offs. send היא async; בקשה שיוצאת מ-unmount לא תוכל לדווח שגיאה למסך שכבר לא קיים. זה עדיין עדיף על אובדן שקט. סיכון רגרסיה בינוני-נמוך; useDraftAutosave.test.ts (233 שורות) מכסה את ההתנהגות ויצטרך תוספת מקרה. דורש שינוי התנהגותי.

### F10 — FactLifecyclePanel עושה יותר מדי Medium / High ✅ בוצע

334 שורות. מעורבים: query לרשימת עובדות, query לפרטים, effect לבחירה אוטומטית (:53-57), שלוש mutations, עשרה useState לשדות טופס (:62-71), ולידציה ידנית ב-canCreate (:130), ו-JSX של שלושה אזורים.

זו הקומפוננטה היחידה בקוד שלא משתמשת ב-useAppForm למרות שיש לה טופס בן 7 שדות. כל שאר הטפסים כן. הן ה-Field/Select/TextArea שהיא מרנדרת בנויים לעבוד עם register.

המלצה — פיצול לשלושה, לא יותר:

- FactLifecyclePanel (container: queries + בחירה)
- FactHistoryActions — היסטוריה + confirm/promote + attach (props: factId, status, profile, sections)
- CreatePendingFactForm — עובר ל-useAppForm, מוחק את 7 ה-useState ואת canCreate לטובת validate (props: profile, onCreated)

מה לא לפצל. אין טעם לחלץ את factLabel/sourceLabels/styleLabels לקומפוננטות — הן שייכות ל-factLabels.ts של F6.

Trade-offs. error = a ?? b ?? c ?? d ?? e (:128) מקפל חמש שגיאות שונות לכותרת אחת ("לא ניתן לעדכן את העובדה") — כשל בקריאת הרשימה מוצג כאילו כשלה מוטציה. הפיצול פותר את זה בדרך אגב. אין טסט על הקומפוננטה; רגרסיה תיתפס רק ידנית.

### F11 — חילוצים מ-DraftEditorPage Medium / High ✅ בוצע

| רכיב מוצע | מה מחולץ | props | היקף | מיקום |
| --- | --- | --- | --- | --- |
| DraftHeaderCard | :103-135 — חברה/תפקיד, v{n}·hash, badge, DraftSaveState | autosave, detail, draft | feature | pages/draft-editor/ |
| DraftSectionCard | :206-264 — כותרת פרק, כפתור יצירה מחדש, רשימת טענות | section, sectionIndex, draft, detail, facts, applicationId, claimHandlers, onRegenerateSection | feature | pages/draft-editor/ |

DraftSectionCard הוא החילוץ בעל הערך: הוא מבודד את הענף claims.length === 0, מקצר את הרינדור, ומאפשר לבדוק פרק בלי לטעון עורך שלם. בדרך הוא גם מסלק את השכפול של חמש ה-props הזהות ל-DraftClaimCard בשלושה אתרים (:180-189, :191-201, :238-259) — כדאי לאגד אותן לאובייקט claimHandlers אחד.

הערה על ה-hook. useDraftEditorState מחזיר 25 שדות. זה גדול, אבל לא הייתי מפצל אותו: כל השדות תלויים ב-draft/detail המשותפים, וחלוקה תיצור שני hooks שמעבירים זה לזה מצב. useDraftAutosave כבר מפוצל ממנו נכון. זה גבול נכון.

### F12 — הלוח פותח 10 שאילתות רשימה לרינדור Medium / High

ApplicationListPage.tsx:99-121: 4 שאילתות preset + 5 שאילתות pipelineStages, כולן limit: 1, נקראות רק בשביל matched. בתוספת שאילתת הרשימה עצמה — 10 בקשות.

בצד השרת (projections.py:124-142) list_applications מקרין את כל המועמדויות ואז מסנן בזיכרון ב-narrow_application_list. כלומר כל אחת מה-10 מבצעת את הפרויקציה המלאה. עם 200 מועמדויות זה 2,000 פרויקציות לרינדור אחד, ופי 10 בכל הקלדה בחיפוש (אחרי ה-debounce של 300ms).

זה לא באג — זה עובד ונכון סמנטית, ועל בסיס נתונים של משתמש יחיד זה כנראה נסבל. אבל זה עלות שגדלה לינארית ופי 10.

המלצה. אם/כשזה נמדד כאיטי: להוסיף preset_counts ו-recruitment_status_counts לתשובת ApplicationListResponse, בדיוק כפי ש-stage_counts כבר עושה שם (queries.py:190-195) ומאותו נימוק. 10 בקשות → 1. דורש שינוי חוזה ולכן את מלוא ה-gate של F4. לא הייתי עושה את זה לפני מדידה.

### F13 — queries.py מחזיק שלוש אחריויות Medium / Medium

895 שורות בקובץ אחד, שלושה סוגי תוכן:

- DTOs — ~30 מחלקות BoundaryDTO (:33-660)
- לוגיקת רשימה — _matches_preset, _is_closed, _matches_search, _sort_key, _Descending, narrow_application_list, _matches_activity (:259-444)
- mappers — application_view, draft_outline_view, recruitment_timeline_view ועוד (:667-895)

הלוגיקה באמצע היא היחידה שיש בה החלטות מוצריות (מה נסגר, מה נחשב ראיון פעיל, מה סדר השלבים) והיא קבורה בין הגדרות טיפוסים. commands.py (698) סובל מאותו דבר — פקודות + תוצאות.

המלצה. חבילה cv_engine/application/queries/ עם views.py / narrowing.py / mappers.py ו-__init__.py שמייצא מחדש. הספק מתיר זאת במפורש: "Subpackages are introduced only when the amount and cohesion of code justify them" — 895 שורות עם שלוש אחריויות עומדות בזה, ותקדים קיים ב-services/drafts/ ו-services/operations/.

Trade-offs. רק תזוזת קבצים. __init__.py שמייצא מחדש שומר על כל ה-imports הקיימים, אז הסיכון קרוב לאפס — אבל גם התועלת המיידית קטנה. אני לא ממליץ לעשות את זה עכשיו אלא כשמשהו באזור הזה משתנה ממילא. מוגן ע"י test_application_list_query.py ו-test_architecture.py (שרץ רקורסיבית ולכן ימשיך לכסות).

### F14 — Loading states לא עקביים Low / High ✅ בוצע

יש primitive טוב, QueryState, ו-8 קבצים משתמשים בו. שניים לא:

- ArtifactsPanel.tsx:205-207: if (query.error === null && ordered.length === 0) return null; — בזמן הטעינה ordered ריק ואין שגיאה, אז הפאנל כולו נעלם ואז קופץ. הקורא לא יודע שהוא מחכה למשהו.
- CanonicalFactsBrowser.tsx:53-66: סולם isPending → error → empty → content בנוי ביד — בדיוק מה ש-QueryState+EmptyState עושים, ושה-SettingsPage שמכיל אותו משתמש בהם שתי שורות למעלה (SettingsPage.tsx:53-60).

המלצה. להעביר את שניהם ל-QueryState. יש כאן אחידות סמנטית אמיתית, אז ה-primitive מוצדק — ורק לכן אני ממליץ.

### F15/F16/F17 — כפילויות קטנות עם primitive קיים Low / High ✅ בוצע

F15: ApplicationListPage.tsx:255-277 בונה role="group" + aria-pressed + מפת classes ל-toggle תצוגה — בדיוק מה ש-ui/ViewSwitch.tsx הוא, כולל ה-classes bg-cv-surface text-cv-accent shadow-surface. ההבדל היחיד: הגרסה ב-ViewSwitch היא label טקסטואלי והגרסה בלוח היא icon. פתרון: icon?: LucideIcon ל-ViewSwitchOption. אם ההבדל הויזואלי מכוון (padding/גודל), עדיף להשאיר כפול ולתעד — אבל אז צריך לומר את זה בהערה, וכרגע לא נאמר.
F16: applicationListPresentation.ts:5-10 — formatApplicationDate הוא Intl formatter רביעי, עם אותה הגנת isNaN של formatDateTime. פתרון: DateTimeStyle נוסף "date", ומחיקת המקומי.
F17: התבנית "בטל detail + list" מופיעה ב-8 מקומות ולא עקבית: await+void בסדר הפוך (ApplicationListPage.tsx:137-138 מול :144-145), Prefix מול Key(id), ומקומות שמבטלים רק את אחד מהשניים. פתרון: invalidateApplicationViews(queryClient, applicationId?) ב-api/applications.ts. זה כן שווה — הבחירה בין prefix ל-key ספציפי היא כרגע החלטה שכל קורא לוקח מחדש, וזו הסיבה לחוסר העקביות.

### F18/F19/F20/F21 — נקודתיים Low

F18: NewApplicationPage.tsx:150-160 ו-QuickIntakeDialog.tsx:99-101 בולעים את השגיאה מ-startAnalysis לגמרי. ההחלטה לא להיכשל נכונה (המועמדות והתצלום כבר קיימים). מה שאבד הוא הסיבה: המשתמש רואה "המועמדות נוצרה, אך הניתוח לא הופעל" (JobDetailsPage.tsx:172) בלי לדעת אם זה מפתח AI חסר, worker כבוי, או נפילת רשת. פתרון: להחזיר analysisProblem: ProblemDetails | null ב-SubmitResult ולהציג את ה-detail בתוך ה-callout. הבחנה חשובה: זה expected failure שנרשם, לא unexpected — כרגע הוא מטופל כאילו אין הבדל.
F19: RecruitmentExceptionalActions.tsx:78 — new Date(fields.submittedAt).toISOString() בלי בדיקה, בעוד useRevisionPageState.ts:107 כן שומר submittedAtValid. required + datetime-local חוסמים את הרוב, אבל אותו טרנספורם ראוי לפונקציה אחת עם אותה הגנה — במיוחד כי localDateTimeInputValue (הכיוון ההפוך) כבר מרוכזת ב-ui/ ואף מכוסה בטסט.
F20: useWatchedOperation.tsx הוא ה-import היחיד מ-hooks/ ל-pages/ (:7) והוא מחזיר JSX (:81). זה מערבב "מעקב אחרי Operation" (לוגיקה) עם "הנה הפאנל" (תצוגה), ומונע בדיקה בלי DOM. אבל ארבעת הקוראים כולם מציבים operationPanel באותו אופן, אז הפיצול יוסיף 4 שורות JSX כפולות. Trade-off אמיתי — הייתי מפצל רק אם/כשקורא חמישי ירצה פאנל אחר. מזהה, לא ממליץ לשנות עכשיו.
F21: אותו throw new Error("<X> rendered without an applicationId route parameter") ב-JobDetailsPage.tsx:118, ApplicationPage.tsx:24, DraftEditorPage.tsx:35. useRequiredParam("applicationId") ב-app/ היה מרכז את זה. שלוש שורות — גבולי. הייתי עושה את זה רק אם מגיע מסך רביעי.

## ג. מפת כפילויות

| משפחה | מיקומים | מה משותף | מה שונה | לאחד? | Abstraction | בעלות |
| --- | --- | --- | --- | --- | --- | --- |
| Intake | NewApplicationPage :37-241 · QuickIntakeDialog :23-147 | מדיניות קליטה, mutation, מפתח, כפילויות, staleness | JSX בלבד (מסך מלא / דיאלוג) | כן | useApplicationIntake | pages/new-application/ |
| שלבי גיוס | PipelineStagesBar :7-37 · ApplicationAlternativeViews :167-188 · queries.py :246-256 | מיפוי status→שלב | הלוח כולל עמודת סגורים; ה-preset בשרת | כן (FE) — הצגה בלבד, השרת נשאר בעל הסינון | recruitmentStages.ts | pages/application-list/ |
| "סגור" | applicationListPresentation :106 · queries.py :327 | חוק עסקי זהה | שפה בלבד | כן — לשרת | שדה בפרויקציה | application/queries.py |
| "באיחור" | applicationListPresentation :14-27 · UrgentActionHub :31-63 | אותה שאלה | UTC מול מקומי; טיפול ב-non-date | כן | isNextActionOverdue + isDueToday | application-list/ |
| מצבי עובדה | FactLifecyclePanel :41-47 · CanonicalFactsBrowser :14-30,69 | labels + כלל תצוגה | נוסח pending; ל-Browser יש tones/icons | כן | factLabels.ts | pages/facts/ |
| גרסה ישנה | useRevisionPageState :95-106 · applicationLabels :190-195 · השרת | אותה מסקנה | נוסח | כן — למחוק את המקומי | קיימת (warningTitle) | pages/application/ |
| פורמט תאריך | ui/formatDateTime · applicationListPresentation :5-10 | Intl + הגנת NaN | style בלבד | כן | style: "date" | ui/ |
| View switch | ApplicationListPage :255-277 · ui/ViewSwitch | group/aria-pressed/classes | icon מול label | כן (prop) | קיימת | ui/ |
| Invalidation | 8 אתרים | "detail + list" | await/void, prefix/key | כן | invalidateApplicationViews | api/applications.ts |
| Idempotency keys | 4 אתרי useMemo מול 4 דטרמיניסטיים | מפתח ל-§13 | אסטרטגיה | כן — לדטרמיניסטי | קיימת (דפוס) | לכל קורא |
| datetime→ISO | RecruitmentExceptionalActions :78 · useRevisionPageState :80,107 | אותו טרנספורם | אחד מגן, השני לא | כן | isoFromLocalInput | ui/ |
| הגנת param | 3 מסכים | אותו throw | שם המסך | לא כרגע | — | — |
| ApplicationListParts | Row/Card/Pipeline דרך variant | זהות, badge, next action | 3 variants | לא — כבר אוחד נכון | קיימת | — |
| ui/QueryState → app/ErrorCallout | import אחד "החוצה" | — | — | לא | — | — |

## ד. הצעת ארגון קבצים

רק מה שהייתי משנה. לא בוצע.


```text
frontend/src/
  api/
    useSettings.ts                    ← חדש (F5)
    applications.ts                   ← + invalidateApplicationViews (F17)
  ui/
    formatDateTime.ts                 ← + style "date" (F16)
    isoFromLocalInput.ts              ← חדש, ליד localDateTimeInputValue (F19)
    ViewSwitch.tsx                    ← + icon?: LucideIcon (F15)
  pages/
    facts/                            ← תיקייה חדשה
      factLabels.ts                   ← מ-FactLifecyclePanel + CanonicalFactsBrowser (F6)
      FactLifecyclePanel.tsx          ← עובר מ-pages/ (F10)
      FactHistoryActions.tsx          ← חדש (F10)
      CreatePendingFactForm.tsx       ← חדש, useAppForm (F10)
    new-application/
      useApplicationIntake.ts         ← חדש; מקור לשני משטחי הקליטה (F1)
    application-list/
      recruitmentStages.ts            ← חדש; מקור יחיד לקיבוץ שלבים (F2)
      applicationListPresentation.ts  ← − isApplicationClosed (F4), + isDueToday (F7)
    draft-editor/
      DraftHeaderCard.tsx             ← חדש (F11)
      DraftSectionCard.tsx            ← חדש (F11)

cv_engine/application/
  queries/                            ← אופציונלי, רק כשמשהו כאן משתנה ממילא (F13)
    __init__.py                       ← re-export, שומר על כל ה-imports
    views.py  narrowing.py  mappers.py
```

הערת ownership שלא הייתי מתקן עכשיו: pages/application/applicationLabels.ts מיובא מ-5 תיקיות feature שונות — הוא בפועל מודול משותף שיושב בתוך feature אחד. אותו דבר ל-actionDestinations.ts ו-analysisLabels.ts. תזוזה ל-src/applications/labels/ הייתה מיישרת את המיקום עם הבעלות, אבל היא נוגעת ב-15 imports בתמורה לאפס שינוי התנהגותי. דחייה עד ששינוי אחר יפתח את האזור.

## ה. תוכנית refactor הדרגתית

לפי AGENTS.md: אני לא מריץ טסטים. אלה הפקודות למסירה. אף שלב לא נוגע ב-rendering, ב-artifact path, או ב-schema — למעט שלב 5, שכן.

### שלב 1 — ערך גבוה, סיכון נמוך (ללא שינוי התנהגותי)

קבצים: ui/formatDateTime.ts, ui/ViewSwitch.tsx, ui/isoFromLocalInput.ts, applicationListPresentation.ts, ApplicationListPage.tsx, RecruitmentExceptionalActions.tsx, useRevisionPageState.ts, api/applications.ts + 8 אתרי invalidation.
מכסה: F15, F16, F17, F19, F8.
Dependencies: אין. כל תיקון עצמאי.
סיכון רגרסיה: נמוך. F8 משנה נוסח מוצג — לבדוק ידנית מסך גרסה מוכנה.
פקודות:


```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test -- src/pages/ApplicationListPage.test.tsx src/pages/StageEPages.test.tsx src/ui/localDateTimeInputValue.test.ts
npm --prefix frontend run lint:tokens
```

Rollback: commit לכל תיקון בנפרד.

### שלב 2 — איחוד error / loading (F14, F5, F18)

קבצים: api/useSettings.ts (חדש), useDraftEditorState.ts, AutomaticDraftNotice.tsx, useApplicationActionsMutations.ts, ArtifactsPanel.tsx, CanonicalFactsBrowser.tsx, NewApplicationPage.tsx, QuickIntakeDialog.tsx, JobDetailsPage.tsx.
Dependencies: F18 נוגע בשני קבצי ה-intake — לבצע לפני שלב 4 או להתאים אחריו.
סיכון: בינוני-נמוך. F5 משנה מתי ה-callout "AI לא זמין" מופיע (לטובה).
פקודות:


```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test -- src/pages/draft-editor/DraftEditorPage.test.tsx src/pages/JobDetailsPage.test.tsx src/pages/NewApplicationPage.test.tsx src/pages/application/StaleDraftCommands.test.tsx
```

Rollback: useSettings בקומיט נפרד מהצרכנים.

### שלב 3 — חילוץ חוקים עסקיים וטרנספורמציות (F2, F6, F7, F3)

קבצים: recruitmentStages.ts (חדש), PipelineStagesBar.tsx, ApplicationAlternativeViews.tsx, pages/facts/factLabels.ts (חדש), FactLifecyclePanel.tsx, CanonicalFactsBrowser.tsx, applicationListPresentation.ts, UrgentActionHub.tsx, useApplicationActionsMutations.ts, OperationActions.tsx.
Dependencies: F2 ו-F7 חוסמים על החלטת משתמש (ראה למטה). F3 עצמאי.
סיכון: בינוני. F2 ו-F7 משנים התנהגות באופן גלוי. F3 נוגע בחוזה §13.
כיסוי חסר: אין טסט על PipelineStagesBar, UrgentActionHub, applicationListPresentation. כאן מוצדק להוסיף כיסוי — selectedStage ו-isNextActionOverdue הם פונקציות טהורות שנבדקות בזול, ו-applicationActionPlan.test.ts הוא התקדים המדויק.
פקודות:


```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test -- src/pages/ApplicationListPage.test.tsx src/pages/application/StaleDraftCommands.test.tsx src/pages/application/applicationActionPlan.test.ts
npm --prefix frontend run test        # הסוויטה המלאה בסוף הגבול
npm --prefix frontend run e2e -- shell.spec.ts job-details.spec.ts
```

Rollback: F3 (מפתחות) בקומיט משלו — הוא היחיד עם חשיפה לשרת.

### שלב 4 — פיצול קומפוננטות (F1, F10, F11, F9)

קבצים: useApplicationIntake.ts (חדש), NewApplicationPage.tsx, QuickIntakeDialog.tsx, pages/facts/* (3 קבצים), DraftHeaderCard.tsx + DraftSectionCard.tsx (חדשים), DraftEditorPage.tsx, useDraftAutosave.ts.
Dependencies: F1 אחרי שלב 2 (F18 נוגע באותו mutationFn). F9 עצמאי אבל שייך לאותו גבול.
סיכון: F1 — בינוני, כי לדיאלוג אין טסט. F9 — בינוני, נוגע ב-autosave. F10/F11 — נמוך (תזוזת JSX).
כיסוי חסר: QuickIntakeDialog, FactLifecyclePanel. מוצדק טסט חדש ל-useApplicationIntake (יחליף כיסוי לשני המשטחים בבת אחת) ומקרה unmount ב-useDraftAutosave.test.ts.
פקודות:


```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test -- src/pages/NewApplicationPage.test.tsx src/pages/draft-editor/useDraftAutosave.test.ts src/pages/draft-editor/DraftEditorPage.test.tsx
npm --prefix frontend run test        # סוויטה מלאה בסגירת הגבול
npm --prefix frontend run e2e -- new-application.spec.ts
```

Rollback: useApplicationIntake + NewApplicationPage בקומיט אחד, QuickIntakeDialog בשני — כך שאפשר לחזור על אחד מהם בלבד.

### שלב 5 — שינויי חוזה ומבנה (F4, F12, F13) — רק אם מוצדק

קבצים: queries.py, openapi/types.ts (מיוצר), applicationListPresentation.ts, 3 צרכנים.
Dependencies: אחרי כל השאר.
סיכון: גבוה יחסית — שינוי בשדה פרויקציה.

⚠️ לפי AGENTS.md, שינוי במשמעות ערך מאוחסן / חתימה ציבורית / שדה פרויקציה גורר את מלוא ה-gate:


```bash
pytest tests/test_application_list_query.py tests/test_state_projection.py
pytest tests/test_architecture.py
python openapi/generate_openapi.py          # ואז לוודא שה-diff מכיל רק את השדה החדש
OPENAI_API_KEY= pytest tests/test_pipeline_end_to_end.py   # מול PostgreSQL נקי
pytest -m "not browser"                     # פעם אחת בסגירת הגבול
npm --prefix frontend run typecheck && npm --prefix frontend run test
```

אין שינוי rendering/artifact path, ולכן golden hashes וסוויטת הדפדפן לא נדרשים בשלב הזה.

Rollback: F4 בקומיט אחד הפיך; F13 (תזוזת קבצים בלבד) בקומיט נפרד וניתן להפרדה מוחלטת.

## ו. מה בדקתי והחלטתי להשאיר

| מה | למה לא לגעת |
| --- | --- |
| ApplicationListRow / ApplicationCard / PipelineCard | נראים דומים, אבל ApplicationListParts.tsx כבר חילץ את המשותף עם variant. השאר הוא פריסה שונה באמת. איחוד נוסף היה יוצר קומפוננטה עם 3 ענפים ואפס משותף. |
| useDraftEditorState עם 25 יציאות | גדול, אבל כל השדות תלויים באותו draft/detail. פיצול ייצור שני hooks שמעבירים מצב זה לזה. useDraftAutosave כבר מפוצל ממנו במקום הנכון. |
| ui/QueryState → app/ErrorCallout | ה-import היחיד "החוצה" מ-ui/. העברת ErrorCallout ל-ui/ רק תחליף תלות ב-app/ בתלות ב-api/. אפס רווח. |
| hooks/useWatchedOperation מחזיר JSX | גבול לא נקי (F20), אבל 4 הקוראים זהים; הפיצול מוסיף כפילות במקום להסיר. לשקול מחדש עם קורא חמישי. |
| שלוש הגנות applicationId | 3 שורות. useRequiredParam הוא indirection ששווה רק במסך רביעי. |
| preparationStateLabels / recruitmentStatusLabels / operationLabels / analysisLabels נפרדים | אוצרות מילים שונים לאמיתם, כל אחד ממופתח על union אחר. ריכוז ל-constants גלובלי היה מוחק בדיוק את הבטיחות שהם מספקים. |
| applicationListParams.ts — 5 טבלאות Record<T, true> | נראה שכפול של ה-unions, אבל זו ההגנה: ערך מה-URL חייב להיבדק מול סט סגור, והממצאות שוברת build. זה guard נגזר לפי AGENTS.md, לא כפילות. |
| שני קבצי הכפילות duplicateCheck (לקוח) + הבדיקה בפקודת ה-create (שרת) | תועד במפורש ב-applications.ts:89-93 כשתי ריצות בכוונה. השרת סמכותי. לא כפילות. |
| מפות ה-toneClasses ב-Callout/StatusBadge/PipelineStagesBar | אותם מפתחות, classes שונים לחלוטין ובמכוון (רקע רך מול גבול צבעוני). ריכוז היה קושר שלוש החלטות ויזואליות עצמאיות. |
| except Exception ב-backend (21 אתרים) | כולם cleanup-then-raise או wrap-with-context. אין בליעה. הטיפול משמעתי. |
| אכיפת שכבות ב-backend | ARCHITECTURE_DEBT_ALLOWLIST ריק, PERSISTENCE_KNOWN_OFFENDERS ריק, _modules רקורסיבי. זה בדיוק ה"derived guard" ש-AGENTS.md דורש. אין מה לשפר. |

### Blockers — סתירות שדורשות הכרעה שלך

לא פירשתי אף אחת מהן בשקט.

- F2 — קיבוץ השלבים. assignment ו-final_stage מקובצים אחרת בסרגל הפילטר ובלוח. אי אפשר לאחד בלי להחליט איזה מהשניים נכון מוצרית.
- ✅ F7 הוכרע — next_action_date הוא יום קלנדרי מקומי, בהתאם להגדרת "לפני היום" במפרט ולערך date-only בצד השרת.
- F4/F12 — האם לשלם את מחיר ה-gate. שניהם משפרים את הארכיטקטורה אבל גוררים את בדיקת הצנרת הדטרמיניסטית המלאה. F4 מסיר סתירה מול AGENTS.md ולכן מוצדק יותר; F12 הוא אופטימיזציה שלא נמדדה ואני לא ממליץ עליה לפני מדידה.
- F3 — חלון מפתחות ה-idempotency. מפתח דטרמיניסטי ל-retry אומר שניסיון חוזר אחרי כשל קבוע יחזיר תשובה שמורה. צריך לאשר מול §13 שזו ההתנהגות הרצויה.
### 10 הפעולות המומלצות, בסדר ביצוע

1. ✅ בוצע — F1 — לחלץ useApplicationIntake ולמחוק ~120 שורות כפולות מ-QuickIntakeDialog. (ההשפעה הגדולה ביותר; צד אחד לא מכוסה בטסטים כלל)
2. ✅ בוצע — F3 — להמיר 4 מפתחות useMemo+UUID למפתחות נגזרים, כמו ארבעת הדטרמיניסטיים שכבר קיימים.
3. ✅ בוצע — F2 — להכריע את קיבוץ השלבים ולרכז ב-recruitmentStages.ts. (אי-עקביות גלויה למשתמש)
4. ✅ בוצע — F5 — useSettings() במקום שלושה enabled:false; לתקן את הבהוב ה-callout בעורך.
5. ✅ בוצע — F9 — flush ל-autosave ב-unmount; נוסף מקרה ל-useDraftAutosave.test.ts.
6. ✅ בוצע — F7 — אוחד חישוב "באיחור" ונוסף לו כיסוי טהור.
7. ✅ בוצע — F6 + F8 — נוסף factLabels.ts; אוצר המילים של warnings רוכז תוך שמירת ההבחנה בין הגרסה המוצגת לגרסה המוכנה האחרונה.
8. ✅ בוצע — F14 + F17 + F16 + F15 — סבב primitives: QueryState, invalidateApplicationViews, formatDateTime, ViewSwitch.
9. ✅ בוצע — F10 + F11 — לפצל FactLifecyclePanel (ולהעביר ל-useAppForm) ולחלץ DraftSectionCard + DraftHeaderCard.
10. F4 — להעביר את חוק "מועמדות סגורה" לפרויקציה, עם מלוא ה-gate. (אחרון: היחיד שנוגע בחוזה)
11. F12, F13, F18–F21 — לתעד ולדחות עד ששינוי אחר יפתח את האזור.
