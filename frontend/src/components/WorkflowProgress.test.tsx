import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import GenerationProgress from "./GenerationProgress";
import ParticipantTable from "./ParticipantTable";
import type { Participant } from "../types";

const participant: Participant = {
  id: "1",
  row_number: 2,
  name: "Ada",
  email: "ada@example.edu",
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
  updated_at: null,
  error_reason: null,
  delivery_reference: "ref",
  previous_delivery: null,
  attempts: [],
};

describe("GenerationProgress", () => {
  it("shows live generation totals and activity", () => {
    render(
      <GenerationProgress
        progress={{
          job_id: "job",
          status: "RUNNING",
          total: 10,
          succeeded: 4,
          failed: 1,
          remaining: 5,
          percent: 50,
          current_name: "Grace",
          started_at: null,
          finished_at: null,
        }}
      />,
    );
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/Grace/)).toBeInTheDocument();
    expect(screen.getByText(/Generated:/)).toHaveTextContent("4");
    expect(screen.getByText(/Failed:/)).toHaveTextContent("1");
  });
});

describe("ParticipantTable editing", () => {
  it("auto-saves on blur and reports saved state", async () => {
    const patch = vi.fn().mockResolvedValue(undefined);
    render(<ParticipantTable rows={[participant]} onPatch={patch} />);
    const input = screen.getByLabelText("Name for ada@example.edu");
    fireEvent.change(input, { target: { value: "Ada Lovelace" } });
    fireEvent.blur(input);
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith("1", { name: "Ada Lovelace" }),
    );
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });
});
