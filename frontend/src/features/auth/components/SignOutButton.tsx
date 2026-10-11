import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { logout } from "@/api/auth";
import { routePaths } from "@/navigation/routePaths";
import { buttonClasses } from "@/ui/Button";
import { Tooltip } from "@/ui/Tooltip";
import { clearSignedInBrowserState } from "../session";

/* Ends this session and leaves nothing of the reader in the browser. A sign-out the
   server could not record still clears the browser: the reader asked to leave. */
export const SignOutButton = ({ compact = false }: { compact?: boolean }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const signOut = useMutation({
    mutationFn: logout,
    onSettled: () => {
      clearSignedInBrowserState(queryClient);
      void navigate(routePaths.login(), { replace: true });
    },
  });
  const button = (
    <button
      aria-label="התנתקות"
      className={buttonClasses("ghost", compact ? undefined : "lg:w-full", compact ? "icon" : "default")}
      disabled={signOut.isPending}
      onClick={() => signOut.mutate()}
      type="button"
    >
      <LogOut aria-hidden="true" className="size-icon-md" />
      {compact ? null : <span className="hidden sm:inline">התנתקות</span>}
    </button>
  );

  return compact ? (
    <Tooltip label="התנתקות" placement="rail">
      {button}
    </Tooltip>
  ) : (
    button
  );
};
