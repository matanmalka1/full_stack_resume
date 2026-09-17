import { useState } from "react";
import { Button, Dialog } from "cv-application-frontend";

export const OpenState = () => (
  <div className="relative" style={{ minHeight: 320 }}>
    <Dialog
      open={true}
      onClose={() => {}}
      headingId="dlg-preview-1"
      title="אישור מחיקה"
      footer={
        <div className="flex gap-2">
          <Button variant="destructive">מחק</Button>
          <Button variant="ghost">ביטול</Button>
        </div>
      }
    >
      <p className="text-body text-cv-text">
        האם למחוק את הגרסה הזו של קורות החיים? לא ניתן לשחזר פעולה זו.
      </p>
    </Dialog>
  </div>
);

export const WithForm = () => {
  const [open, setOpen] = useState(true);
  return (
    <div className="relative" style={{ minHeight: 380 }}>
      <Button variant="secondary" onClick={() => setOpen(true)}>פתח דיאלוג</Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        headingId="dlg-preview-2"
        title="הוספת ניסיון"
        footer={
          <div className="flex gap-2">
            <Button variant="primary">שמור</Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>ביטול</Button>
          </div>
        }
      >
        <p className="text-support text-cv-text-muted">
          מלא את הפרטים הרלוונטיים להוספה לפרופיל.
        </p>
      </Dialog>
    </div>
  );
};
