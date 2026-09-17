import { Checkbox, Field, FormSection, Input } from "cv-application-frontend";

export const Default = () => (
  <div className="p-4 max-w-sm">
    <FormSection title="פרטים אישיים" description="מידע בסיסי להצגה בקורות החיים">
      <Field label="שם מלא">{(ctrl) => <Input {...ctrl} placeholder="ישראל ישראלי" />}</Field>
      <Field label="כתובת מייל">{(ctrl) => <Input {...ctrl} type="email" placeholder="name@example.com" />}</Field>
    </FormSection>
  </div>
);

export const WithAside = () => (
  <div className="p-4 max-w-sm">
    <FormSection title="כישורים" aside="3 נבחרו" description="הכישורים הרלוונטיים למשרה">
      <Checkbox defaultChecked>React</Checkbox>
      <Checkbox defaultChecked>TypeScript</Checkbox>
      <Checkbox>Node.js</Checkbox>
      <Checkbox defaultChecked>SQL</Checkbox>
    </FormSection>
  </div>
);
