import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import StatusCards from "./StatusCards";
import AllowanceCards from "./AllowanceCards";
import type { Batch } from "../types";
import ParticipantTable from "./ParticipantTable";
import type { Participant } from "../types";
describe("StatusCards", () => {
  it("renders persisted delivery counts", () => {
    const batch = {
      counts: {
        TOTAL: 10,
        PENDING: 3,
        SENDING: 1,
        SENT: 5,
        FAILED: 1,
        UNCERTAIN: 0,
      },
    } as Batch;
    render(<StatusCards batch={batch} />);
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Uncertain")).toBeInTheDocument();
  });
});
describe("AllowanceCards", () => {
  it("shows the optional app cap, activity, and provider notice", () => {
    render(
      <AllowanceCards
        allowance={{
          enabled: true,
          limit: 200,
          used: 8,
          remaining: 192,
          successful: 7,
          failed: 2,
          uncertain: 1,
          notice: "Provider limits apply.",
        }}
      />,
    );
    expect(screen.getByText("192 / 200")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Provider limits apply.")).toBeInTheDocument();
  });
});
describe("ParticipantTable", () => {
  it("shows mailto recipient links, durable status, and update time", () => {
    const participant = {
      id: "1",
      row_number: 2,
      name: "Ada",
      email: "ada@example.edu",
      is_valid: true,
      is_excluded: false,
      validation_error: null,
      status: "SENT",
      filename: "ada.pdf",
      certificate_current: true,
      legibility_warning: null,
      smtp_message_id: "message",
      sent_at: "2026-10-22T12:00:00Z",
      updated_at: "2026-10-22T12:00:00Z",
      error_reason: null,
    } as Participant;
    render(<ParticipantTable rows={[participant]} />);
    expect(
      screen.getByRole("link", { name: "ada@example.edu" }),
    ).toHaveAttribute("href", "mailto:ada@example.edu");
    expect(screen.getByText("SENT")).toBeInTheDocument();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });
});
