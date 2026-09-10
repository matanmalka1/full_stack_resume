import { useMutation, useQueryClient } from "@tanstack/react-query";

import { closeApplication, invalidateApplicationViews } from "@/api/applications";
import type { RecruitmentStatus } from "@/api/contracts";
import { correctRecruitmentStatus, setNextAction } from "@/api/tracking";

interface ApplicationListMutationOptions {
  onApplicationClosed: (applicationId: string, eventId: string | null | undefined) => void;
  onCloseUndone: () => void;
  onNextActionCleared: (applicationId: string) => void;
}

/** Keeps command state and cache invalidation out of list presentation. */
export const useApplicationListMutations = ({
  onApplicationClosed,
  onCloseUndone,
  onNextActionCleared,
}: ApplicationListMutationOptions) => {
  const queryClient = useQueryClient();

  const closeMutation = useMutation({
    mutationFn: closeApplication,
    onSuccess: async (result, applicationId) => {
      onApplicationClosed(applicationId, result.event_id);
      await invalidateApplicationViews(queryClient, applicationId);
    },
  });

  const undoCloseMutation = useMutation({
    mutationFn: ({
      applicationId,
      eventId,
      previousStatus,
    }: {
      applicationId: string;
      eventId: string;
      previousStatus: RecruitmentStatus;
    }) =>
      correctRecruitmentStatus(applicationId, {
        corrects_event_id: eventId,
        reason: "ביטול סגירת המועמדות",
        target_status: previousStatus,
      }),
    onSuccess: async (_result, variables) => {
      onCloseUndone();
      await invalidateApplicationViews(queryClient, variables.applicationId);
    },
  });

  const clearNextActionMutation = useMutation({
    mutationFn: (applicationId: string) => setNextAction(applicationId, { next_action: null, next_action_date: null }),
    onSuccess: async (_result, applicationId) => {
      onNextActionCleared(applicationId);
      await invalidateApplicationViews(queryClient, applicationId);
    },
  });

  return { clearNextActionMutation, closeMutation, undoCloseMutation };
};
