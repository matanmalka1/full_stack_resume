import { Button, EmptyState } from "cv-application-frontend";

export const Default = () => (
  <div className="p-4 max-w-sm">
    <EmptyState>
      <p className="text-body font-semibold text-cv-text">אין הגשות עדיין</p>
      <p className="mt-1 text-support text-cv-text-muted">הוסף משרה כדי להתחיל</p>
    </EmptyState>
  </div>
);

export const WithAction = () => (
  <div className="p-4 max-w-sm">
    <EmptyState>
      <p className="text-body font-semibold text-cv-text">לא נמצאו תוצאות</p>
      <p className="mt-1 text-support text-cv-text-muted">נסה לשנות את מסנני החיפוש</p>
      <div className="mt-4">
        <Button variant="secondary" size="compact">נקה מסננים</Button>
      </div>
    </EmptyState>
  </div>
);
