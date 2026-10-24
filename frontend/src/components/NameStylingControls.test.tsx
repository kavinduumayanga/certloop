import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Region } from "../types";
import NameStylingControls from "./NameStylingControls";

const initialRegion: Region = {
  x: 0.2,
  y: 0.45,
  w: 0.6,
  h: 0.12,
  font_size: 110,
  min_font_size: 38,
  auto_fit: true,
  vertical_offset: 0,
};

afterEach(cleanup);

function ControlledControls({ onSave = vi.fn() }: { onSave?: () => void }) {
  const [region, setRegion] = useState(initialRegion);
  return (
    <NameStylingControls
      region={region}
      dirty
      saving={false}
      renderedFontSize={92}
      previewWarning={false}
      onChange={(partial) =>
        setRegion((current) => ({ ...current, ...partial }))
      }
      onSave={onSave}
    />
  );
}

describe("NameStylingControls", () => {
  it("keeps the font-size slider and numeric field synchronized", () => {
    render(<ControlledControls />);

    fireEvent.change(screen.getByLabelText("Font Size slider"), {
      target: { value: "144" },
    });

    expect(screen.getByLabelText("Font Size value")).toHaveValue(144);
    expect(screen.getByText("92px")).toBeInTheDocument();
  });

  it("supports precise vertical adjustments and auto-fit changes", () => {
    render(<ControlledControls />);

    fireEvent.click(
      screen.getByRole("button", { name: "Increase vertical offset" }),
    );
    expect(screen.getByLabelText("Vertical Offset value")).toHaveValue(1);

    fireEvent.click(screen.getByRole("switch", { name: "Auto-fit Long Names" }));
    expect(
      screen.getByRole("switch", { name: "Auto-fit Long Names" }),
    ).not.toBeChecked();
  });

  it("blocks saving an invalid minimum and enables a valid dirty save", () => {
    const onSave = vi.fn();
    render(<ControlledControls onSave={onSave} />);

    const save = screen.getByRole("button", { name: "Save Placement" });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledOnce();

    fireEvent.change(screen.getByLabelText("Minimum Font Size value"), {
      target: { value: "200" },
    });
    expect(screen.getByText("Must not exceed the font size")).toBeInTheDocument();
    expect(save).toBeDisabled();
  });

  it("shows saved state and disables save when nothing changed", () => {
    render(
      <NameStylingControls
        region={initialRegion}
        dirty={false}
        saving={false}
        renderedFontSize={0}
        previewWarning={false}
        onChange={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText("Placement is saved")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save Placement" }),
    ).toBeDisabled();
  });
});
