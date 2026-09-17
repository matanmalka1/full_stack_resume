import { Button, SectionHeader } from "cv-application-frontend";
import { Briefcase, Star } from "lucide-react";

export const Default = () => (
  <div className="p-4 max-w-lg">
    <SectionHeader title="ניסיון מקצועי" />
  </div>
);

export const WithDescription = () => (
  <div className="p-4 max-w-lg">
    <SectionHeader
      title="כישורים נבחרים"
      description="הכישורים שנבחרו יופיעו בקורות החיים המותאמים"
    />
  </div>
);

export const WithIcon = () => (
  <div className="p-4 max-w-lg">
    <SectionHeader
      title="ניסיון בחברות"
      icon={Briefcase}
      iconPresentation="badge"
      description="היסטוריית התעסוקה מ-CV Base"
    />
  </div>
);

export const WithActions = () => (
  <div className="p-4 max-w-lg">
    <SectionHeader
      title="הישגים מרכזיים"
      icon={Star}
      iconPresentation="inline"
      actions={<Button size="compact" variant="secondary">הוסף הישג</Button>}
    />
  </div>
);
