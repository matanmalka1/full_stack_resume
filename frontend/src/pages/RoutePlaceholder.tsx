import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";

interface RoutePlaceholderProps {
  title: string;
  description?: string;
}

export const RoutePlaceholder = ({ title, description }: RoutePlaceholderProps) => {
  /* A not-found or not-yet-built route is on no stage of the workflow, and saying so is
     what keeps the landmark from carrying the previous screen's stage into it. */
  useWorkflowStage("none");

  return (
    <Card aria-labelledby="route-heading">
      {/* No eyebrow and no default description. Both were development scaffolding -
          a milestone code and a promise that the screen was still being built - shown
          to someone who had simply followed a broken link. */}
      <PageHeading description={description} id="route-heading">
        {title}
      </PageHeading>
    </Card>
  );
};
