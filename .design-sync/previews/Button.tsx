import { Button } from "cv-application-frontend";

export const Variants = () => (
  <div className="flex flex-wrap gap-3 p-4">
    <Button variant="primary">פעולה ראשית</Button>
    <Button variant="secondary">פעולה משנית</Button>
    <Button variant="ghost">פעולה רכה</Button>
    <Button variant="destructive">מחיקה</Button>
  </div>
);

export const Sizes = () => (
  <div className="flex flex-wrap items-center gap-3 p-4">
    <Button size="compact" variant="secondary">קומפקט</Button>
    <Button size="default">ברירת מחדל</Button>
  </div>
);

export const States = () => (
  <div className="flex flex-wrap gap-3 p-4">
    <Button variant="primary" pending pendingLabel="שומר...">שמירה</Button>
    <Button variant="secondary" disabled>מבוטל</Button>
    <Button variant="destructive" disabled>מבוטל</Button>
  </div>
);
