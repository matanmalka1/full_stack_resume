# TODO — ממצאי UX Frontend

## P1 — קריטי

- [ ] **Zoom/Pan במסמך** — `DraftWorkspace`, `RevisionPage`: הוסף בקרות זום (100% / Fit / +/-) מעל `DocumentFrame`, אפשר גלילה דו-ממדית במסכים צרים/mobile. כרגע CSS scale מכווץ ללא זום אינטראקטיבי.
- [ ] **Undo/Redo בעריכת טיוטה** — `useDraftEditing`: מחסנית עריכות מקומית (Ctrl+Z / revert claim), לפני שה-autosave (1.5s debounce) שולח לשרת. כרגע אין שחזור לניסוח קודם.
- [ ] **עריכת פרופיל/מסלול/דגשים אחרי פתיחת מועמדות** — הוסף פעולת "ערוך הגדרות התאמה" ב-`VerificationStage`/`JobSnapshotPanel` + טריגר re-analyze. כרגע נעול לצמיתות אחרי הפתיחה. **בדוק קודם spec** (`docs/spec/state-and-use-cases.md`) אם re-analyze מותר בלייף-סייקל.
- [ ] **ביטול/Retry בפעולות רקע** — `ActiveOperationPanel`: הוסף `cancelOperation`, שלבי התקדמות מוחשיים (לא ספינר גנרי), כפתור Retry בכל הודעת כישלון.
- [ ] **רענון אוטומטי אחרי אישור עובדה** — `ClaimFactResolution`: הפעל רענון אימות טיוטה אוטומטי אחרי אישור מוצלח, עדכן תג שורה (בלתי נתמכת→מאומתת) מיידית בלי לחיצה ידנית.
- [ ] **הסר תלות ב-`location.state`** — Wizard steps: בסס state רק על URL + `ApplicationDetail.preparation_progress` מהשרת. כרגע F5/טאב חדש מאפס הקשר.

## P2 — שיפור

- [ ] **העתקה מהירה כטקסט/Markdown** — כפתור "העתק תוכן קורות חיים" ב-`RevisionPage` וב-`DraftWorkspace` (ל-Greenhouse/Comeet/Workday/LinkedIn).
- [ ] **הרחבת חיפוש גלובלי** — `GlobalSearchDialog`: הסר הגבלת `limit: 8`, הוסף חיפוש ב-Facts וטיוטות היסטוריות, קישור ל"כל התוצאות".
- [ ] **ולידציה בטופס עדכון משרה** — `JobPostingUpdate`: בדיקת תקינות URL בצד קליינט, dirty-diff מול הנוסח הקיים לפני שליחה.
- [ ] **איחוד Dialog primitive** — כל המודלים (`GlobalSearchDialog`, `ClaimFactResolution` וכו') דרך רכיב דיאלוג אחיד עם focus trap + escape + return focus.

## סדר מומלץ

1. #5 (רענון אימות) → #6 (location.state) → #3 (עריכת פרופיל) — ליבה תפקודית
2. #1 (Zoom/Pan) → #4 (Cancel/Retry) — שימוש יומיומי
3. #2 (Undo)
4. P2 — לפי צורך
