import { Input, Textarea } from "cv-application-frontend";

export const TextInputs = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <Input placeholder="שם מלא" />
    <Input type="email" placeholder="name@example.com" />
    <Input type="number" placeholder="0" />
    <Input value="טקסט קיים" onChange={() => {}} />
    <Input disabled placeholder="לא זמין" />
  </div>
);

export const TextareaVariants = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <Textarea placeholder="תאר את הניסיון שלך…" rows={3} />
    <Textarea disabled placeholder="לא ניתן לעריכה" rows={2} />
  </div>
);
