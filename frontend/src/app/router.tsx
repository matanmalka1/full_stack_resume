import type { ComponentType } from "react";
import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { QueryState } from "@/ui/QueryState";
import { AppLayout } from "./layout/AppLayout";
import { NotFoundPage } from "./layout/NotFoundPage";
import { RootRouteErrorBoundary, RouteErrorBoundary } from "./layout/RouteErrorBoundary";

/* The preparation workflow is carried by the board, intake, the Application hub, its
   preparation tab, the draft editor, and the ready document. Candidate facts and
   settings are durable product areas outside that per-Application workflow.

   Validation, approval, and render are not among them. Each was a screen holding a single
   button, and each acted on the draft the editor was already showing, so reaching one
   meant leaving the text it described. They are states of the editor now. Review joined
   them: the analysis it decides about is on the Application screen.

   An Operation has no route either. Queueing reports in place, and a direct link lands on
   the Application whose panel shows the run.

   Every screen is its own chunk, loaded when it is first visited, so opening the board
   does not download the draft editor. Navigating keeps the current screen on view until
   the next one has arrived; only the very first load has nothing to show, and there the
   shell renders and the content column says it is loading. A chunk that fails to load is
   a route error like any other and lands in the boundary below.

   The loaders name the page module itself rather than the feature's index. The indexes
   are also imported by the shell and by other features, so a dynamic import of one would
   be folded back into the main chunk and split nothing. */

const screen =
  <Module,>(load: () => Promise<Module>, pick: (module: Module) => ComponentType) =>
  async () => ({ Component: pick(await load()) });

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    /* The shell's own failure. Nothing above it is left to render, so the boundary here
       stands alone and carries its own way out. */
    errorElement: <RootRouteErrorBoundary />,
    children: [
      {
        /* A pathless route whose only job is to own the boundary for every screen below
           it. A screen that throws used to take the whole shell down with it - the
           boundary sat on the route that renders `AppLayout`, so replacing it removed the
           masthead, the primary navigation and the search palette along with the screen,
           and a reader who hit a 500 was left with a red card and the browser's own back
           button. Owned here, the boundary replaces the `Outlet` and the shell stays. */
        errorElement: <RouteErrorBoundary />,
        hydrateFallbackElement: <QueryState loading loadingLabel="טוען…" />,
        children: [
          {
            index: true,
            lazy: screen(
              () => import("@/features/application-list/pages/ApplicationListPage"),
              (module) => module.ApplicationListPage,
            ),
          },

          /* Creating is one action taken from the board, not what the root does. */
          {
            path: "applications/new",
            lazy: screen(
              () => import("@/features/application-intake/pages/NewApplicationPage"),
              (module) => module.NewApplicationPage,
            ),
          },

          /* The Application hub: its job record, its CV preparation, and its artifacts, on
         one screen with one address. */
          {
            path: "applications/:applicationId",
            lazy: screen(
              () => import("@/features/applications/pages/ApplicationPage"),
              (module) => module.ApplicationPage,
            ),
          },
          {
            path: "applications/:applicationId/resume",
            lazy: screen(
              () => import("@/features/applications/pages/ApplicationResumePage"),
              (module) => module.ApplicationResumePage,
            ),
          },

          /* The draft editor: edit, preview, check, approve, and render, on the one screen
         that holds the document all five act on. */
          {
            path: "applications/:applicationId/draft",
            lazy: screen(
              () => import("@/features/drafts/pages/DraftEditorPage"),
              (module) => module.DraftEditorPage,
            ),
          },

          /* The ready step: the rendered document, its PDF and the record of sending it.
             A state of the Application's one document rather than a record of its own, so
             it is addressed by the Application like the editor beside it - and the way back
             to editing is always there, because editing a Ready document is allowed and
             simply returns it to draft. */
          {
            path: "applications/:applicationId/ready",
            lazy: screen(
              () => import("@/features/ready/pages/ReadyPage"),
              (module) => module.ReadyPage,
            ),
          },

          {
            path: "facts",
            lazy: screen(
              () => import("@/features/facts/pages/FactsPage"),
              (module) => module.FactsPage,
            ),
          },
          {
            path: "settings",
            lazy: screen(
              () => import("@/features/settings/pages/SettingsPage"),
              (module) => module.SettingsPage,
            ),
          },

          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
