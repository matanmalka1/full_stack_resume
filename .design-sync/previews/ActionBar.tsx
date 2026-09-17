import { ActionBar, Button } from "cv-application-frontend";

export const Split = () => (
  <div className="p-4">
    <ActionBar
      primary={<Button variant="primary">שמור ושלח</Button>}
      secondary={<Button variant="ghost">ביטול</Button>}
    />
  </div>
);

export const EndAlign = () => (
  <div className="p-4">
    <ActionBar
      primary={<Button variant="primary">המשך</Button>}
    />
  </div>
);

export const StartAlign = () => (
  <div className="p-4">
    <ActionBar
      align="start"
      primary={<Button variant="primary">שמור טיוטה</Button>}
      secondary={<Button variant="secondary">תצוגה מקדימה</Button>}
    />
  </div>
);
