import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button, buttonClasses } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { PageShell } from "@/ui/PageShell";

interface AppErrorBoundaryProps {
  children: ReactNode;
  homePath?: string;
}

interface AppErrorBoundaryState {
  error: Error | null;
}

/* Route failures have a closer boundary that can preserve the application shell. This
   one sits above every provider as the final fallback for failures that happen before
   the router can render or outside its route tree. */
export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  public state: AppErrorBoundaryState = { error: null };

  public static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const context: Record<string, unknown> = {
      componentStack: errorInfo.componentStack,
      message: error.message,
      name: error.name,
    };

    if (import.meta.env.DEV) context.stack = error.stack;

    console.error("app_error_boundary", context);
  }

  private reload = (): void => {
    window.location.reload();
  };

  public render(): ReactNode {
    const { error } = this.state;

    if (error === null) return this.props.children;

    return (
      <main className="page-gutter min-h-screen py-12">
        <PageShell
          description="לא ניתן להמשיך כרגע. אפשר לטעון מחדש את האפליקציה או לחזור לדף הבית."
          eyebrow="תקלה באפליקציה"
          eyebrowTone="blocker"
          measure="form"
          title="אירעה שגיאה בלתי צפויה"
        >
          <Card className="p-card-padding" role="alert">
            <div className="flex flex-wrap gap-field-gap">
              <Button onClick={this.reload}>טעינה מחדש</Button>
              <a className={buttonClasses("secondary")} href={this.props.homePath ?? import.meta.env.BASE_URL}>
                חזרה לדף הבית
              </a>
            </div>

            {import.meta.env.DEV ? (
              <details className="mt-section-gap">
                <summary className="cursor-pointer font-semibold">
                  פרטי שגיאה לפיתוח
                </summary>
                <pre className="mono-code mt-field-gap overflow-auto whitespace-pre-wrap text-support">
                  {`${error.toString()}${error.stack ? `\n\n${error.stack}` : ""}`}
                </pre>
              </details>
            ) : null}
          </Card>
        </PageShell>
      </main>
    );
  }
}
