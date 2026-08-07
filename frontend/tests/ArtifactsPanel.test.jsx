import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ArtifactsPanel from "../components/ArtifactsPanel";

describe("ArtifactsPanel", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:artifact");
    URL.revokeObjectURL = vi.fn();
  });

  it("can attach the latest artifact version back to Chat as explicit context", () => {
    const onAttachArtifact = vi.fn();
    render(
      <ArtifactsPanel
        onAttachArtifact={onAttachArtifact}
        artifacts={[
          {
            id: "artifact-1",
            title: "Fuel summary",
            type: "text",
            versions: [
              { version: 1, content: "old summary" },
              { version: 2, content: "latest summary" },
            ],
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Attach to Chat" }));

    expect(onAttachArtifact).toHaveBeenCalledWith({
      label: "Fuel summary",
      source: "artifact",
      kind: "text",
      content: "latest summary",
      artifactId: "artifact-1",
      version: 2,
    });
  });

  it("downloads the selected artifact version", () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(
      <ArtifactsPanel
        artifacts={[
          {
            id: "artifact-1",
            title: "Demo HTML",
            type: "html",
            versions: [{ version: 2, content: "<html><body>Two</body></html>" }],
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    expect(URL.createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:artifact");
    click.mockRestore();
  });
});
