import { Switch } from "cv-application-frontend";

export const States = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <Switch checked={false} onChange={() => {}}>קבלת עדכונים במייל</Switch>
    <Switch checked={true} onChange={() => {}}>קבלת עדכונים במייל</Switch>
    <Switch checked={false} disabled onChange={() => {}}>מבוטל</Switch>
    <Switch checked={true} disabled onChange={() => {}}>מבוטל ומופעל</Switch>
  </div>
);

export const WithDescription = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <Switch
      checked={true}
      onChange={() => {}}
      description="תקבל הודעה בכל פעם שמעמד הגשה משתנה"
    >
      עדכוני מעמד הגשה
    </Switch>
    <Switch
      checked={false}
      onChange={() => {}}
      description="שיתוף נתוני שימוש אנונימיים לשיפור המוצר"
    >
      שיתוף אנליטיקה
    </Switch>
  </div>
);
