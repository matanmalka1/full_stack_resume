interface RoutePlaceholderProps {
  title: string;
  description?: string;
}

const defaultDescription = "תוכן המסך יתווסף בשלב היישום הייעודי שלו.";

export const RoutePlaceholder = ({ title, description }: RoutePlaceholderProps) => {
  return (
    <section
      aria-labelledby="route-heading"
      className="rounded-xl border border-cv-border bg-cv-surface p-8"
    >
      <p className="mb-2 text-sm font-semibold text-cv-accent">M4 · תשתית הממשק</p>
      <h1
        className="text-3xl font-semibold tracking-tight outline-none"
        data-route-heading
        id="route-heading"
        tabIndex={-1}
      >
        {title}
      </h1>
      <p className="mt-4 max-w-2xl leading-7 text-cv-text-muted">
        {description ?? defaultDescription}
      </p>
    </section>
  );
};
