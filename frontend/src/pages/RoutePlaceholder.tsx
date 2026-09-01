import { useWorkflowStage } from "../app/WorkflowLandmark";
import { PageShell } from "../ui/PageShell";

interface RoutePlaceholderProps {
  title: string;
  description?: string;
}

export const RoutePlaceholder = ({ title, description }: RoutePlaceholderProps) => {
  /* A not-found or not-yet-built route is on no stage of the workflow, and saying so is
     what keeps the landmark from carrying the previous screen's stage into it. */
  useWorkflowStage("none");

  return <PageShell description={description} title={title} />;
};
