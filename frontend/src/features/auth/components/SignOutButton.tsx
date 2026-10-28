import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { logout } from "@/api/auth";
import { routePaths } from "@/navigation/routePaths";
import { buttonClasses } from "@/ui/Button";
import { clearSignedInBrowserState } from "../session";

/* Ends this session and leaves nothing of the reader in the browser. A sign-out the
   server could not record still clears the browser: the reader asked to leave.

   `className` replaces the ghost button's look rather than adding to it, for the
   sidebar, which draws sign-out as one of its rows. */
export const SignOutButton = ({ className }: { className?: string }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const signOut = useMutation({
    mutationFn: logout,
    onSettled: () => {
      clearSignedInBrowserState(queryClient);
      void navigate(routePaths.login(), { replace: true });
    },
  });
  return (
    <button
      className={
        className === undefined
          ? buttonClasses("ghost")
          : `inline-flex items-center transition-colors disabled:cursor-not-allowed ${className}`
      }
      disabled={signOut.isPending}
      onClick={() => signOut.mutate()}
      type="button"
    >
      <LogOut aria-hidden="true" className="size-icon-md" />
      <span>התנתקות</span>
    </button>
  );
};
