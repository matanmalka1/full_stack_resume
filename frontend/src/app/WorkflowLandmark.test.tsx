import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { ApplicationDetail } from "../api/contracts";
import {
  useWorkflowStage,
  WorkflowLandmark,
  WorkflowLandmarkSteps,
  type WorkflowStage,
  workflowDestinations,
} from "./WorkflowLandmark";

const detail = (overrides: Partial<ApplicationDetail>) => overrides as ApplicationDetail;

const Screen = ({
  destinations,
  stage,
}: {
  destinations?: ReturnType<typeof workflowDestinations>;
  stage: WorkflowStage;
}) => {
  useWorkflowStage(stage, destinations);
  return null;
};

const landmark = (
  stage: WorkflowStage,
  destinations?: ReturnType<typeof workflowDestinations>,
  pathname = "/somewhere",
) =>
  render(
    <MemoryRouter initialEntries={[pathname]}>
      <WorkflowLandmark>
        <WorkflowLandmarkSteps />
        <Screen destinations={destinations} stage={stage} />
      </WorkflowLandmark>
    </MemoryRouter>,
  );

const hrefs = () =>
  Object.fromEntries(
    screen.queryAllByRole("link").map((link) => [link.textContent?.trim(), link.getAttribute("href")]),
  );

describe("workflowDestinations", () => {
  it("offers the editor only once a working draft exists", () => {
    expect(workflowDestinations("app-1", detail({}))).toEqual({
      intake: "/applications/app-1",
      analysis: "/applications/app-1/preparation",
    });
    expect(workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" }))).toMatchObject({
      draft: "/applications/app-1/draft",
      validation: "/applications/app-1/draft",
    });
  });

  /* A rendered revision is what "מוכן" means to the reader; the approved one answers only
     while no render exists yet. */
  it("names the ready revision, preferring the rendered one", () => {
    expect(workflowDestinations("app-1", detail({ latest_approved_revision_id: "rev-a" })).ready).toBe(
      "/revisions/rev-a",
    );
    expect(
      workflowDestinations("app-1", detail({ latest_approved_revision_id: "rev-a", latest_ready_revision_id: "rev-b" }))
        .ready,
    ).toBe("/revisions/rev-b");
  });
});

describe("workflow landmark navigation", () => {
  it("links every stage the projection has reached, and nothing ahead of it", () => {
    landmark("ready_for_approval", workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" })));

    /* Current is אימות, whose screen is the editor - a link, because the reader is on the
       preparation screen and not on it. מוכן is ahead and has no revision to open. */
    expect(hrefs()).toEqual({
      "משרה חדשה": "/applications/app-1",
      ניתוח: "/applications/app-1/preparation",
      טיוטה: "/applications/app-1/draft",
      אימות: "/applications/app-1/draft",
    });
    expect(screen.getByRole("link", { name: "מעבר לשלב אימות" })).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("link", { name: "חזרה לשלב ניתוח" })).not.toHaveAttribute("aria-current");
  });

  it("does not link the screen already being read", () => {
    landmark(
      "ready_for_approval",
      workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" })),
      "/applications/app-1/draft",
    );

    /* Both stages the editor holds drop their link on the editor itself. */
    expect(hrefs()).not.toHaveProperty("טיוטה");
    expect(hrefs()).not.toHaveProperty("אימות");
    expect(screen.getByText("טיוטה")).toBeInTheDocument();
  });

  /* With nothing behind it the landmark stays an indicator rather than announcing a
     navigation landmark with no destinations in it. */
  it("stays an indicator on the intake screen", () => {
    landmark("intake");

    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByRole("img")).toHaveAccessibleName(/שלב 1 מתוך 5/);
  });

  it("announces a completed workflow when Ready has no current step", () => {
    landmark("ready", workflowDestinations("app-1", detail({ latest_ready_revision_id: "rev-1" })));

    expect(screen.getByRole("navigation")).toHaveAccessibleName("שלבי הכנת קורות החיים: הושלם, 5 מתוך 5");
    expect(screen.getByRole("link", { name: "פתיחת שלב מוכן" })).toHaveAttribute("href", "/revisions/rev-1");
  });
});
