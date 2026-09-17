import { Checkbox } from "cv-application-frontend";

export const States = () => (
  <div className="flex flex-col p-4 max-w-sm">
    <Checkbox>אני מאשר שהפרטים נכונים</Checkbox>
    <Checkbox defaultChecked>הצג ניסיון קודם</Checkbox>
    <Checkbox disabled>מבוטל</Checkbox>
    <Checkbox disabled defaultChecked>מבוטל ומסומן</Checkbox>
  </div>
);

export const WithHint = () => (
  <div className="flex flex-col p-4 max-w-sm">
    <Checkbox hint="קורות חיים יישלחו ישירות למגייס">
      שלח אוטומטית לאחר אישור
    </Checkbox>
    <Checkbox hint="מידע זה לא יופיע בקורות החיים">
      סמן כחסוי
    </Checkbox>
  </div>
);
