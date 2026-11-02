import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TemplateGallery } from "./TemplateGallery";

describe("TemplateGallery", () => {
  it("sketches each thumbnail until its own page paints", () => {
    const { container } = render(
      <TemplateGallery
        name="template"
        onChange={() => undefined}
        options={[]}
        previewSrc={(template) => `/preview?template=${template}`}
        value={null}
      />,
    );
    expect(container.querySelector(".cv-skeleton")).not.toBeNull();

    fireEvent.load(screen.getByTitle("תצוגה מקדימה: תבנית המסלול"));
    expect(container.querySelector(".cv-skeleton")).toBeNull();
  });
});
