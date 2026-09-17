import { Card, StatusBadge } from "cv-application-frontend";

export const Default = () => (
  <div className="p-4 max-w-sm">
    <Card className="p-card-padding">
      <p className="text-body font-semibold text-cv-text">מפתח Full-Stack</p>
      <p className="mt-1 text-support text-cv-text-muted">Google · 2021–היום</p>
    </Card>
  </div>
);

export const WithBadge = () => (
  <div className="flex flex-col gap-3 p-4 max-w-sm">
    <Card className="p-card-padding">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-body font-semibold text-cv-text">Frontend Engineer</p>
          <p className="mt-0.5 text-support text-cv-text-muted">Meta · 2019–2021</p>
        </div>
        <StatusBadge tone="success">מאושר</StatusBadge>
      </div>
    </Card>
    <Card className="p-card-padding">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-body font-semibold text-cv-text">Backend Engineer</p>
          <p className="mt-0.5 text-support text-cv-text-muted">Startup · 2018–2019</p>
        </div>
        <StatusBadge tone="warning">בבדיקה</StatusBadge>
      </div>
    </Card>
  </div>
);

export const StatusRole = () => (
  <div className="p-4 max-w-sm">
    <Card role="status" className="p-card-padding text-center text-support text-cv-text-muted">
      טוען נתונים…
    </Card>
  </div>
);
