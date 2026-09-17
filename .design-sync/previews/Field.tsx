import { Field, Input } from "cv-application-frontend";

export const Basic = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <Field label="שם מלא">{(ctrl) => <Input {...ctrl} placeholder="ישראל ישראלי" />}</Field>
    <Field label="כתובת מייל" optional>{(ctrl) => <Input {...ctrl} type="email" placeholder="name@example.com" />}</Field>
  </div>
);

export const WithHint = () => (
  <div className="p-4 max-w-sm">
    <Field label="תפקיד נוכחי" hint="ישמש לכותרת קורות החיים">
      {(ctrl) => <Input {...ctrl} placeholder="מפתח בכיר" />}
    </Field>
  </div>
);

export const WithError = () => (
  <div className="p-4 max-w-sm">
    <Field label="שנות ניסיון" error="אנא הזן מספר חיובי">
      {(ctrl) => <Input {...ctrl} type="number" value="" onChange={() => {}} />}
    </Field>
  </div>
);
