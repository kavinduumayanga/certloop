import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Participant } from "../types";
import GeneratedCertificatePanel from "./GeneratedCertificatePanel";

const participant = (
  overrides: Partial<Participant> & Pick<Participant, "id" | "name" | "email">,
): Participant => ({
  row_number: 2,
  is_valid: true,
  is_excluded: false,
  validation_error: null,
  status: "PENDING",
  filename: null,
  certificate_current: false,
  legibility_warning: null,
  generation_error: null,
  smtp_message_id: null,
  sent_at: null,
  updated_at: "2026-10-24T10:00:00Z",
  error_reason: null,
  delivery_reference: "ref",
  previous_delivery: null,
  attempts: [],
  ...overrides,
});

const sent = participant({
  id: "sent-id",
  name: "Ada Lovelace",
  email: "ada@example.edu",
  status: "SENT",
  filename: "ada.pdf",
  certificate_current: true,
});
const pending = participant({
  id: "pending-id",
  name: "Grace Hopper",
  email: "grace@example.edu",
});

afterEach(cleanup);

describe("GeneratedCertificatePanel", () => {
  it("previews, downloads, and allows regenerating a SENT participant", () => {
    const regenerate = vi.fn();
    render(
      <GeneratedCertificatePanel
        participants={[sent, pending]}
        selectedId={sent.id}
        generationRunning={false}
        regeneratingId={null}
        onSelect={vi.fn()}
        onRegenerate={regenerate}
      />,
    );

    expect(
      screen.getByAltText("Generated certificate for Ada Lovelace"),
    ).toHaveAttribute("src", expect.stringContaining("/sent-id/preview"));
    expect(screen.getByRole("link", { name: /Download/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/sent-id/certificate"),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Regenerate Certificate" }),
    );
    expect(regenerate).toHaveBeenCalledWith("sent-id");
  });

  it("supports searching and switching participants", () => {
    const select = vi.fn();
    render(
      <GeneratedCertificatePanel
        participants={[sent, pending]}
        selectedId={sent.id}
        generationRunning={false}
        regeneratingId={null}
        onSelect={select}
        onRegenerate={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByLabelText("Open"));
    fireEvent.click(screen.getByRole("option", { name: /Grace Hopper/ }));
    expect(select).toHaveBeenCalledWith("pending-id");
  });

  it("shows empty and outdated states without generating automatically", () => {
    const regenerate = vi.fn();
    const outdated = { ...sent, certificate_current: false };
    const { rerender } = render(
      <GeneratedCertificatePanel
        participants={[outdated]}
        selectedId={outdated.id}
        generationRunning={false}
        regeneratingId={null}
        onSelect={vi.fn()}
        onRegenerate={regenerate}
      />,
    );
    expect(screen.getByText(/older template or placement/)).toBeInTheDocument();
    expect(regenerate).not.toHaveBeenCalled();

    rerender(
      <GeneratedCertificatePanel
        participants={[pending]}
        selectedId={pending.id}
        generationRunning
        regeneratingId={pending.id}
        onSelect={vi.fn()}
        onRegenerate={regenerate}
      />,
    );
    expect(screen.getByText(/No certificates have been generated/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Regenerate Certificate" }),
    ).toBeDisabled();
  });
});
