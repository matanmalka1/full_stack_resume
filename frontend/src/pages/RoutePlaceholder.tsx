import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";

interface RoutePlaceholderProps {
  title: string;
  description?: string;
}

const defaultDescription = "תוכן המסך יתווסף בשלב היישום הייעודי שלו.";

export const RoutePlaceholder = ({ title, description }: RoutePlaceholderProps) => {
  return (
    <Card aria-labelledby="route-heading">
      <PageHeading
        description={description ?? defaultDescription}
        eyebrow="M4 · תשתית הממשק"
        id="route-heading"
      >
        {title}
      </PageHeading>
    </Card>
  );
};
