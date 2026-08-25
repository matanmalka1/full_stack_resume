import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";

interface RoutePlaceholderProps {
  title: string;
  description?: string;
}

const defaultDescription = "תוכן המסך יתווסף בשלב היישום הייעודי שלו.";

export const RoutePlaceholder = ({ title, description }: RoutePlaceholderProps) => {
  /* A not-found or not-yet-built route is on no stage of the workflow, and saying so is
     what keeps the landmark from carrying the previous screen's stage into it. */
  useWorkflowStage("none");

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
