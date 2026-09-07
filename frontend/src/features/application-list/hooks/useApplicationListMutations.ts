import { useMutation, useQueryClient } from "@tanstack/react-query";

import { closeApplication, invalidateApplicationViews } from "@/api/applications";
import { setNextAction } from "@/api/tracking";

interface ApplicationListMutationOptions {
  onApplicationClosed: (applicationId: string) => void;
  onNextActionCleared: (applicationId: string) => void;
}

/** Keeps command state and cache invalidation out of list presentation. */
export const useApplicationListMutations = ({
  onApplicationClosed,
  onNextActionCleared,
}: ApplicationListMutationOptions) => {
  const queryClient = useQueryClient();

  const closeMutation = useMutation({
    mutationFn: closeApplication,
    onSuccess: async (_result, applicationId) => {
      onApplicationClosed(applicationId);
      await invalidateApplicationViews(queryClient, applicationId);
    },
  });

  const clearNextActionMutation = useMutation({
    mutationFn: (applicationId: string) => setNextAction(applicationId, { next_action: null, next_action_date: null }),
    onSuccess: async (_result, applicationId) => {
      onNextActionCleared(applicationId);
      await invalidateApplicationViews(queryClient, applicationId);
    },
  });

  return { clearNextActionMutation, closeMutation };
};
