# Frontend — משימות סידור

מיפוי מצב לפי עמוד, ומה צריך לעשות. סדר העבודה: קודם השכבה המשותפת (חלק 0),
אחריה עמוד-עמוד. כל שינוי כאן הוא מבני בלבד — התנהגות, ניסוח וסמנטיקת המוצר
לא משתנים אלא אם צוין במפורש.

---

## 0. השכבה המשותפת — חסרה לגמרי

היום אין שכבת ביניים בין `ui/` (פרימיטיבים) ל־`pages/` (מסך שלם). כל עמוד
מרכיב את אותם דפוסים מחדש. זה מקור רוב חוסר-האחידות למטה, ולכן זה קודם.

- [ ] **`ui/PageShell.tsx`** — עוטף `Card` + `PageHeading` + אזור פעולות במאסטהד
      + ריווח גוף אחיד. היום כל עמוד כותב `<Card aria-labelledby="route-heading">`
      ידנית ובוחר לבד `mt-6` / `mt-5` / `pb-4` / `pb-5`.
- [ ] **`ui/QueryState.tsx`** (או `PageState`) — מקום אחד למצב טעינה/שגיאה/ריק.
      היום: 6 ניסוחי טעינה שונים, ובחלק מהעמודים הטעינה בגוף ובחלק ב־
      `PageHeading description`.
- [ ] **`app/ErrorCallout` — ברירות מחדל** — `"הפנייה לשרת נכשלה. אפשר לרענן את
      העמוד ולנסות שוב."` מופיע מילה במילה בלפחות 4 קבצים. שיהיה ברירת המחדל של
      הרכיב; `fallbackDetail` רק לחריגים.
- [ ] **`Button` — prop `pending`** — היום `{x.isPending ? "שומר…" : "שמירה"}`
      כתוב ידנית ב־~25 מקומות, וגם `disabled` נגזר ידנית בכל אחד.
- [ ] **`EmptyState`** — הבלוק `rounded-surface border border-dashed p-8 text-center`
      משוכפל 3 פעמים רק ב־ApplicationListPage.
- [ ] **`useWatchedOperation` + `ActiveOperationPanel`** — 3 עמודים חוזרים על אותו
      שילוב. לאחד ל־hook אחד שמחזיר גם את הפאנל המוכן.
- [ ] **רוחב העמוד יוצהר ע"י העמוד** — היום `App.tsx` עושה `useMatch` על שני
      נתיבים ספציפיים כדי להחליט `max-w`. ה־shell לא אמור להכיר עמודים בשם.
- [ ] **`useWorkflowStage` — לוודא שלא נשכח** — כל עמוד קורא ידנית עם לוגיקה שונה
      (`"none"` / `"unknown"` / תלוי view). לשקול חוזה שנכשל בלי הצהרה.

## 0.1 מבנה תיקיות

היום `pages/` שטוח עם 40+ קבצים; רק `application-list/` קיבל תת-תיקייה — והיא
דווקא הדגם הנכון.

- [ ] **`pages/application/`** — `AnalysisPanel`, `JobSnapshotPanel`,
      `ReviewDecisionPanel*`, `ApplicationActions`, `applicationActionPlan`,
      `applicationLabels`, `analysisLabels`, `actionDestinations`, `autoDraft`.
- [ ] **`pages/draft-editor/`** — 12+ קבצי `Draft*.tsx`, `useDraftAutosave`,
      `draftLabels`, `claimRemoval`, `ClaimFactResolution`, `DraftFactPanel`.
- [ ] **`pages/recruitment/`** — `RecruitmentPanel` (442 שורות) ומה שסביבו.
- [ ] **`pages/revision/`**, **`pages/settings/`** — `ReconciliationPanel`,
      `ValidationReportView`.
- [ ] **`hooks/`** — `useDebouncedValue`, `useWatchedOperation` אינם קבצי עמוד.

---

## 1. `/` — ApplicationListPage (191 שורות)

**מצב: הבריא ביותר.** היחיד עם תת-תיקייה, חלוקה נכונה
(Filters / Table / Row / Pagination / Dialog / presentation). זה הדגם.

- [ ] שלושת מצבי הריק (`isPending`, `total===0`, `items.length===0`) → `EmptyState`.
- [ ] `useEffect` עם `eslint-disable react-hooks/exhaustive-deps` לסנכרון
      חיפוש→URL. שביר; להעביר לדפוס שלא דורש השתקה.
- [ ] שני מסלולים ל־`setParams`: `narrow()` שכופה `offset:0`, ובנפרד ה־pagination
      שקורא `setParams` ישירות. לאחד.
- [ ] הטרנרי המקונן של גוף העמוד (`isPending → undefined → total===0 → …`) יפורק
      ע"י `QueryState`.

## 2. `/applications/:id` — ApplicationPage (350 שורות)

**מצב: הכי בעייתי מבחינת אחריות.** מחזיק שני מסכים בקובץ אחד דרך
`?view=tracking`, כשענף ה־tracking הוא בפועל `RecruitmentPanel` בן 442 שורות.

- [ ] **להכריע על ציר ה־tracking.** ה־router מתעד בכוונה למה זה view ולא route
      (מאסטהד משותף, אותה קריאת projection, אותו טיפול שגיאות) — ההחלטה סבירה,
      אבל **המימוש** לא חולק בהתאם: העמוד מחזיק את שני העצים במלואם.
      לפצל ל־`PreparationView` / `TrackingView` תחת `pages/application/`,
      כשהעמוד רק בוחר ביניהם. **החלטת מוצר — לאשר לפני ביצוע.**
- [ ] **auto-draft ב־module scope** — `const autoDraftInFlight = new Set<string>()`
      + מפתחות `localStorage`, כלוגיקת side-effect בתוך קובץ עמוד. להוציא ל־hook
      ייעודי עם בעלות ברורה על המצב.
- [ ] 11 בלוקים אחים של `Callout`/`map` ברצף שטוח (review_reasons, stale_reasons,
      warnings, newer_draft, automaticAnalysisStartFailed). לקבץ לרכיב התראות אחד
      עם סדר מוגדר.
- [ ] `ReasonCallout` מוגדר inline בקובץ — להוציא.
- [ ] `IMPLIES_NO_DRAFT` + `draftStateIsImplied` — לוגיקת תצוגה שמקומה ב־labels/presentation.

## 3. `/applications/:id/draft` — DraftEditorPage (565 שורות — הגדול ביותר)

**מצב: הצפוף ביותר.** מחזיק 5 מצבים (עריכה/תצוגה/אימות/אישור/רינדור).
לפי ה־router זו החלטה מכוונת ומנומקת — הבעיה היא שהקובץ לא חולק בהתאם.

- [ ] `unsaved || regeneration.isPending || !regenerationAvailable` — **חוזר 4 פעמים
      copy-paste**. משתנה נגזר אחד.
- [ ] הטרנרי המקונן התלת-שכבתי ששומר על כל הגוף
      (`renderRevisionId → draft===undefined → workingDraftId===null`).
- [ ] ה־layout ה־responsive (`ViewSwitch` + `lg:hidden` + `hidden lg:flex` + חלוקת
      `basis-7/12`) כתוב inline בעמוד. להוציא ל־`SplitPane`/`EditorLayout`.
- [ ] כל `Draft*.tsx` ל־`pages/draft-editor/`.
- [ ] 5 מופעי `ErrorCallout` בקובץ אחד — יצטמצמו אחרי חלק 0.

## 4. `/revisions/:id` — RevisionPage (319 שורות)

- [ ] `if (approvedRevisionId === undefined) throw` יושב **אחרי** קריאות hooks.
      עובד, אבל שביר לשינוי סדר. להזיז לשומר route או לתחילת הרכיב.
- [ ] אתחול תאריך ההגשה: `useState(() => ...)` עם חישוב offset של timezone inline.
      להוציא לפונקציה נבדקת.
- [ ] 5 מופעי `ErrorCallout` — יצטמצמו אחרי חלק 0.
- [ ] `ValidationReportView` ל־`pages/revision/`.

## 5. `/applications/new` — NewApplicationPage (367 שורות)

**מצב: הדפוס הנכון, שאף עמוד אחר לא ירש.** היחיד שמשתמש ב־`useAppForm` +
`FormSection` + `ActionBar`.

- [ ] אין כאן חוב מבני משמעותי. **להשתמש בו כתקן לכל עמוד שיש בו טופס** (ראה 6).
- [ ] `JobTextFileField`, `DuplicateChoices` ל־`pages/new-application/`.

## 6. `/settings` — SettingsPage (92 שורות)

**מצב: חריגה סגנונית בולטת.** שורות ארוכות מאוד ו־JSX דחוס בשורה אחת, בעוד כל
שאר הקבצים מפורמטים רחב. סימן שהקובץ נכתב מחוץ לדפוס.

- [ ] **לפרמט לפי שאר הקוד.** לבדוק למה Prettier/ESLint לא תפסו את זה.
- [ ] `useState` + `useEffect` לסנכרון טופס מ־query, במקום `useAppForm` כמו
      NewApplicationPage. לאחד לדפוס אחד.
- [ ] **`ReconciliationPanel` (191 שורות) מודבק בסוף העמוד** — פעולת תחזוקה על
      הנתונים, לא הגדרת תצוגה. להפריד לאזור משלו בעמוד, לכל הפחות.

## 7. Shell — `App.tsx` (133 שורות)

- [ ] `useMatch("/")` + `useMatch("/applications/:applicationId/draft")` כדי לבחור
      `max-w`. ה־shell מכיר עמודים בשם — להפוך לאחריות העמוד (חלק 0).
- [ ] `isApplicationScreen` — עוד `useMatch` באותה סיבה, כדי להחליט אם ה־breadcrumb
      הוא קישור. אותו תיקון.

---

## מה לא נוגעים בו

- ניסוחים בעברית, מונחי מוצר, ותוכן טקסטואלי — נשארים כפי שהם.
- הערות ההסבר בראש הקבצים (במיוחד `router.tsx`) — הן תיעוד החלטות, נשמרות.
- סמנטיקת workflow, statuses, ומחזור החיים של artifacts.
