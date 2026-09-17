import { StatusBadge } from "cv-application-frontend";

export const Tones = () => (
  <div className="flex flex-wrap gap-3 p-4">
    <StatusBadge tone="success">הושלם</StatusBadge>
    <StatusBadge tone="progress">בתהליך</StatusBadge>
    <StatusBadge tone="warning">בבדיקה</StatusBadge>
    <StatusBadge tone="blocker">חסום</StatusBadge>
    <StatusBadge tone="info">מידע</StatusBadge>
    <StatusBadge tone="neutral">טיוטה</StatusBadge>
  </div>
);

export const WithLabels = () => (
  <div className="flex flex-col gap-4 p-4">
    <div className="flex flex-wrap gap-3">
      <StatusBadge tone="success">ממתין לאישור</StatusBadge>
      <StatusBadge tone="progress">הגשה בתהליך</StatusBadge>
      <StatusBadge tone="warning">דרושה פעולה</StatusBadge>
      <StatusBadge tone="blocker">נדחה</StatusBadge>
    </div>
  </div>
);
