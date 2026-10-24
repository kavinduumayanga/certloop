import { describe, expect, it } from "vitest";
import {
  DEFAULT_EMAIL_BODY,
  DEFAULT_EMAIL_SUBJECT,
  renderEmailTemplate,
} from "./emailTemplate";

describe("email templates", () => {
  it("provides the generic default subject and body", () => {
    expect(DEFAULT_EMAIL_SUBJECT).toBe("Your Certificate of Participation");
    expect(DEFAULT_EMAIL_BODY).toContain("Hi {name},");
    expect(DEFAULT_EMAIL_BODY).toContain("Event Organizing Team");
    expect(DEFAULT_EMAIL_BODY).not.toMatch(/university|company|DevOps|workshop/i);
  });

  it("previews only the saved participant name placeholder", () => {
    expect(
      renderEmailTemplate(
        "Hello {name}. Event: {workshop_name}.",
        "Saved CSV Name",
      ),
    ).toBe("Hello Saved CSV Name. Event: {workshop_name}.");
  });
});
