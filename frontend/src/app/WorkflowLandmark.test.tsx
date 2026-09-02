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
      analysis: "/applications/app-1/preparation",
    });
    expect(workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" }))).toMatchObject({
      draft: "/applications/app-1/draft",
    });
    /* Validation is not a stage, so it is not a destination either: it is a panel of the
       editor, and the editor is the draft stage's own screen. */
    expect(workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" }))).not.toHaveProperty(
      "validation",
    );
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

    /* Current is טיוטה ואימות, whose screen is the editor - a link, because the reader is
       on the preparation screen and not on it. מוכן is ahead and has no revision to
       open. */
    expect(hrefs()).toEqual({
      ניתוח: "/applications/app-1/preparation",
      "טיוטה ואימות": "/applications/app-1/draft",
    });
    expect(screen.getByRole("link", { name: "מעבר לשלב טיוטה ואימות" })).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("link", { name: "חזרה לשלב ניתוח" })).not.toHaveAttribute("aria-current");
  });

  it("does not link the screen already being read", () => {
    landmark(
      "ready_for_approval",
      workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" })),
      "/applications/app-1/draft",
    );

    /* The one stage the editor holds drops its link on the editor itself. */
    expect(hrefs()).not.toHaveProperty("טיוטה ואימות");
    expect(screen.getByText("טיוטה ואימות")).toBeInTheDocument();
  });

  /* With nothing behind it the landmark stays an indicator rather than announcing a
     navigation landmark with no destinations in it. */
  it("stays an indicator while no stage has a screen to open", () => {
    landmark("needs_analysis");

    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByRole("img")).toHaveAccessibleName(/שלב 1 מתוך 3/);
  });

  /* Intake and Job Detail are how the reader reaches the work, not stages of it: the
     three stages start where the CV does, and no screen outside them is counted. */
  it("counts three stages and offers no way to the job record", () => {
    landmark("draft_in_progress", workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" })));

    expect(screen.queryByText("משרה חדשה")).toBeNull();
    expect(Object.values(hrefs())).not.toContain("/applications/app-1");
    expect(screen.getByText("שלב 2 מתוך 3")).toBeInTheDocument();
  });

  /* The provider default is what the shell shows in the frame before the mounted screen
     publishes. A stage there put the steps over the Application list on the way back to
     it - a stage the list never claimed. */
  it("shows nothing until a screen publishes its stage", () => {
    render(
      <MemoryRouter>
        <WorkflowLandmark>
          <WorkflowLandmarkSteps />
        </WorkflowLandmark>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  /* The position and what the stage is for were only in the accessible name, so a sighted
     reader had to count the words - and below md, where the row is shortened, could not
     count them at all. */
  it("states the position and what the open stage is for, in visible text", () => {
    landmark(
      "draft_in_progress",
      workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" })),
      "/applications/app-1/draft",
    );

    expect(screen.getByText("עמוד טיוטה ואימות")).toBeInTheDocument();
    expect(screen.getByText("שלב 2 מתוך 3")).toBeInTheDocument();
    expect(screen.getByText(/ניסוח, אימות מול העובדות ואישור הגרסה/)).toBeInTheDocument();
  });

  /* The screen being read and the stage the work is on are regularly different, and the
     bar used to draw only the second - at `ready_for_approval` read from the preparation
     screen it highlighted the editor's stage, whose screen the reader was not on. */
  it("names the open screen apart from the stage the work is on", () => {
    landmark(
      "ready_for_approval",
      workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" })),
      "/applications/app-1/preparation",
    );

    expect(screen.getByText("עמוד ניתוח")).toBeInTheDocument();
    expect(screen.getByText("העבודה בשלב 2 מתוך 3: טיוטה ואימות")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toHaveAccessibleName(
      "שלבי הכנת קורות החיים: שלב 2 מתוך 3, טיוטה ואימות. העמוד הפתוח: ניתוח",
    );
  });

  it("announces a completed workflow when Ready has no current step", () => {
    landmark("ready", workflowDestinations("app-1", detail({ latest_ready_revision_id: "rev-1" })));

    expect(screen.getByRole("navigation")).toHaveAccessibleName("שלבי הכנת קורות החיים: הושלם, 3 מתוך 3");
    expect(screen.getByRole("link", { name: "פתיחת שלב מוכן" })).toHaveAttribute("href", "/revisions/rev-1");
  });
});
