import { Button, PageShell, StatusBadge } from "cv-application-frontend";

export const Default = () => (
  <div style={{ direction: "rtl", fontFamily: "Heebo, sans-serif" }}>
    <PageShell
      title="ניתוח הגשה"
      eyebrow="Frontend Engineer · Google"
      description="סקירת הדרישות והתאמתן לניסיון שלך"
      actions={<StatusBadge tone="progress">בתהליך</StatusBadge>}
    >
      <p className="text-support text-cv-text-muted">תוכן העמוד מוצג כאן.</p>
    </PageShell>
  </div>
);

export const WithNavigation = () => (
  <div style={{ direction: "rtl", fontFamily: "Heebo, sans-serif" }}>
    <PageShell
      title="בחירת כישורים"
      eyebrow="שלב 2 מתוך 4"
      actions={
        <div className="flex gap-2">
          <Button variant="ghost">חזור</Button>
          <Button variant="primary">המשך</Button>
        </div>
      }
    >
      <p className="text-support text-cv-text-muted">בחר את הכישורים הרלוונטיים.</p>
    </PageShell>
  </div>
);
