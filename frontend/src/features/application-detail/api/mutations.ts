import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteApplication, invalidateApplicationViews } from "@/api/applications";

/* The ending the hub's menu offers for its own record. A deleted record leaves the board,
   so the screen that showed it hands the reader back to the board (`onDeleted`). */
export const useApplicationRecordMutations = (applicationId: string, { onDeleted }: { onDeleted: () => void }) => {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => deleteApplication(applicationId),
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
      onDeleted();
    },
  });

  return { deleteMutation };
};
