import { Button, Callout } from "cv-application-frontend";

export const Tones = () => (
  <div className="flex flex-col gap-4 p-4 max-w-lg">
    <Callout tone="success" title="הגשה הושלמה">קורות החיים נשלחו בהצלחה.</Callout>
    <Callout tone="progress" title="מעבד ניתוח">זה עשוי לקחת מספר שניות.</Callout>
    <Callout tone="warning" title="חסרים פרטים">לא ניתן לאמת את תאריך הסיום.</Callout>
    <Callout tone="blocker" title="לא ניתן להמשיך">חובה לאשר את כל הפרטים לפני שליחה.</Callout>
    <Callout tone="info" title="לידיעתך">ניתן לערוך את הטיוטה עד לאישור.</Callout>
    <Callout tone="neutral" title="טיוטה">השינויים עדיין לא נשמרו.</Callout>
  </div>
);

export const Banner = () => (
  <div className="flex flex-col gap-6 p-4 max-w-lg">
    <Callout emphasis="banner" tone="success" title="קורות החיים מוכנים לשליחה">
      כל הדרישות הוכחו וניתן להגיש.
    </Callout>
    <Callout emphasis="banner" tone="blocker" title="נדרשת פעולה לפני הגשה">
      תיקון העובדה על שנות הניסיון נדרש לפני שליחה.
    </Callout>
  </div>
);

export const WithAction = () => (
  <div className="flex flex-col gap-4 p-4 max-w-lg">
    <Callout
      tone="warning"
      title="גרסה חדשה זמינה"
      action={<Button size="compact" variant="secondary">עדכן עכשיו</Button>}
    >
      תבנית קורות החיים עודכנה.
    </Callout>
  </div>
);
