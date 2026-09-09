import { Navigate, createBrowserRouter, useParams } from "react-router-dom";

import { NewApplicationPage } from "@/features/application-intake";
import { ApplicationListPage } from "@/features/application-list";
import { ApplicationPage } from "@/features/applications";
import { DraftEditorPage } from "@/features/drafts";
import { RevisionPage } from "@/features/revisions";
import { SettingsPage } from "@/features/settings";
import { AppLayout } from "./layout/AppLayout";
import { NotFoundPage } from "./layout/NotFoundPage";
import { RouteErrorBoundary } from "./layout/RouteErrorBoundary";
import { routePaths } from "./routePaths";

/* Six screens carry the workflow: the board, intake, the Application hub, its preparation
   tab, the draft editor, and the approved revision.

   Validation, approval, and render are not among them. Each was a screen holding a single
   button, and each acted on the draft the editor was already showing, so reaching one
   meant leaving the text it described. They are states of the editor now. Review joined
   them: the analysis it decides about is on the Application screen.

   An Operation has no route either. Queueing reports in place, and a direct link lands on
   the Application whose panel shows the run. */

/* `useParams` rather than a splat rewrite: the id is a path segment, and re-encoding it
   through `routePaths` is what keeps an id with a slash or a space landing where it did. */
const ApplicationRedirect = () => {
  const { applicationId } = useParams();

  return <Navigate replace to={routePaths.application(applicationId ?? "")} />;
};

const ReadyRedirect = () => {
  const { revisionId } = useParams();

  return <Navigate replace to={routePaths.revision(revisionId ?? "")} />;
};

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <ApplicationListPage /> },

      /* Creating is one action taken from the board, not what the root does. */
      { path: "applications/new", element: <NewApplicationPage /> },

      /* The Application hub: its job record, its CV preparation, and its artifacts, on
         one screen with one address. */
      { path: "applications/:applicationId", element: <ApplicationPage /> },

      /* The draft editor: edit, preview, validate, approve, and render, on the one screen
         that holds the draft all five act on. */
      { path: "applications/:applicationId/draft", element: <DraftEditorPage /> },

      /* One approved revision, addressed by the revision itself. It stays a screen of its
         own rather than a state of the editor because the links that reach it name a
         specific immutable record, and an Application-keyed screen would answer with
         whatever revision is current instead of the one named. */
      { path: "revisions/:revisionId", element: <RevisionPage /> },

      { path: "settings", element: <SettingsPage /> },

      /* Three addresses kept only for links already written down. `/preparation` was a
         second name for the hub itself; recruitment is a dialog opened from each
         Application screen; and the revision screen is named for the record rather than
         for the state it was in. */
      { path: "applications/:applicationId/preparation", element: <ApplicationRedirect /> },
      { path: "applications/:applicationId/tracking", element: <ApplicationRedirect /> },
      { path: "approved-revisions/:revisionId/ready", element: <ReadyRedirect /> },

      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
