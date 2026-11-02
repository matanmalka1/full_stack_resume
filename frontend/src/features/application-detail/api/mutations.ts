import { useMutation, useQueryClient } from "@tanstack/react-query";

import { closeApplication, deleteApplication, invalidateApplicationViews } from "@/api/applications";

/* The two endings the hub's menu offers for its own record. Closing keeps the reader on
   the record, which now reads as closed; a deleted record leaves the board, so the screen
   that showed it hands the reader back to the board (`onDeleted`). */
export const useApplicationRecordMutations = (applicationId: string, { onDeleted }: { onDeleted: () => void }) => {
  const queryClient = useQueryClient();

  const closeMutation = useMutation({
    mutationFn: () => closeApplication(applicationId),
    onSuccess: () => invalidateApplicationViews(queryClient, applicationId),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteApplication(applicationId),
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
      onDeleted();
    },
  });

  return { closeMutation, deleteMutation };
};
