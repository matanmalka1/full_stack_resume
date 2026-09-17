import { CopyableTextDisclosure } from "cv-application-frontend";

export const WithText = () => (
  <div className="p-4 max-w-lg">
    <CopyableTextDisclosure
      summary="הצג תיאור המשרה"
      label="תיאור המשרה"
      emptyMessage="לא נמצא תיאור למשרה זו"
      text={`אנו מחפשים מפתח Frontend מנוסה עם ניסיון של 3+ שנים ב-React ו-TypeScript.

תחומי אחריות:
- בניית ממשקי משתמש ב-React
- עבודה עם API מסוג REST ו-GraphQL
- שיתוף פעולה עם צוות UX

דרישות:
- ניסיון ב-React 18+
- TypeScript חובה
- ניסיון עם בדיקות: Jest / Playwright`}
    />
  </div>
);

export const Empty = () => (
  <div className="p-4 max-w-lg">
    <CopyableTextDisclosure
      summary="הצג תיאור המשרה"
      label="תיאור המשרה"
      emptyMessage="לא נמצא תיאור למשרה זו"
      text={null}
    />
  </div>
);
