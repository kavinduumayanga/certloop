import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SessionControls from "./SessionControls";
import type { Batch } from "../types";

const session = (id: string, name: string, created_at: string) =>
  ({ id, name, created_at, updated_at: created_at }) as Batch;

afterEach(cleanup);

describe("SessionControls", () => {
  const current = session(
    "11111111-current",
    "Current session",
    "2026-10-24T10:00:00Z",
  );
  const previous = session(
    "22222222-previous",
    "Previous session",
    "2026-10-22T10:00:00Z",
  );

  it("asks for a friendly name and switches sessions without exposing IDs", async () => {
    const create = vi.fn().mockResolvedValue(undefined);
    const select = vi.fn();
    render(
      <SessionControls
        sessions={[current, previous]}
        current={current}
        onCreate={create}
        onSelect={select}
        busy={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "New Session" }));
    fireEvent.change(screen.getByLabelText("Session name"), {
      target: { value: "  DevOps   Workshop  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Session" }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith("DevOps Workshop"),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );

    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(screen.getByText(/Previous session ·/));
    expect(select).toHaveBeenCalledWith(previous.id);
    expect(screen.queryByText(/11111111|22222222/)).not.toBeInTheDocument();
  });

  it("shows duplicate errors inline and keeps the dialog open", async () => {
    const create = vi
      .fn()
      .mockRejectedValue(
        new Error('A session named "DevOps Workshop" already exists'),
      );
    render(
      <SessionControls
        sessions={[current]}
        current={current}
        onCreate={create}
        onSelect={vi.fn()}
        busy={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "New Session" }));
    fireEvent.change(screen.getByLabelText("Session name"), {
      target: { value: "DevOps Workshop" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Session" }));

    expect(
      await screen.findByText(
        'A session named "DevOps Workshop" already exists',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("prevents empty and overlong names before calling the backend", () => {
    const create = vi.fn().mockResolvedValue(undefined);
    render(
      <SessionControls
        sessions={[current]}
        current={current}
        onCreate={create}
        onSelect={vi.fn()}
        busy={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "New Session" }));
    expect(screen.getByRole("button", { name: "Create Session" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Session name"), {
      target: { value: "x".repeat(101) },
    });
    expect(
      screen.getByText("Session name must be 100 characters or fewer"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Session" })).toBeDisabled();
    expect(create).not.toHaveBeenCalled();
  });
});
