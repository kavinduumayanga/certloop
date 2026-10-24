import { describe, expect, it } from "vitest";
import { DEFAULT_EMAIL_BODY, DEFAULT_EMAIL_SUBJECT } from "./emailTemplate";
import {
  emailDraftFromBatch,
  setSessionEmailDraft,
  updateSessionEmailDraft,
  type SessionEmailDrafts,
} from "./sessionEmailState";

const sessionA = {
  id: "session-a",
  sender_email: "sender@example.com",
  email_subject: "Session A subject for {name}",
  email_body: "Session A body for {name}",
};

const sessionB = {
  id: "session-b",
  sender_email: null,
  email_subject: DEFAULT_EMAIL_SUBJECT,
  email_body: DEFAULT_EMAIL_BODY,
};

describe("session email draft isolation", () => {
  it("hydrates and updates drafts using the session ID", () => {
    let drafts: SessionEmailDrafts = {};
    drafts = setSessionEmailDraft(
      drafts,
      sessionA.id,
      emailDraftFromBatch(sessionA),
    );
    drafts = setSessionEmailDraft(
      drafts,
      sessionB.id,
      emailDraftFromBatch(sessionB),
    );

    drafts = updateSessionEmailDraft(drafts, sessionB, {
      email_subject: "Unsaved Session B edit",
    });

    expect(drafts[sessionA.id].email_subject).toBe(
      "Session A subject for {name}",
    );
    expect(drafts[sessionB.id].email_subject).toBe(
      "Unsaved Session B edit",
    );
  });

  it("restores defaults only in the active session draft", () => {
    let drafts: SessionEmailDrafts = {
      [sessionA.id]: emailDraftFromBatch(sessionA),
      [sessionB.id]: {
        ...emailDraftFromBatch(sessionB),
        email_subject: "Customized Session B subject",
        email_body: "Customized Session B body",
      },
    };

    drafts = updateSessionEmailDraft(drafts, sessionB, {
      email_subject: DEFAULT_EMAIL_SUBJECT,
      email_body: DEFAULT_EMAIL_BODY,
    });

    expect(drafts[sessionB.id].email_subject).toBe(DEFAULT_EMAIL_SUBJECT);
    expect(drafts[sessionB.id].email_body).toBe(DEFAULT_EMAIL_BODY);
    expect(drafts[sessionA.id]).toEqual(emailDraftFromBatch(sessionA));
  });

  it("rehydrates the selected session from its persisted API response", () => {
    const refreshed = setSessionEmailDraft(
      {},
      sessionA.id,
      emailDraftFromBatch(sessionA),
    );

    expect(refreshed[sessionA.id]).toEqual({
      sender_email: "sender@example.com",
      email_subject: "Session A subject for {name}",
      email_body: "Session A body for {name}",
    });
    expect(refreshed[sessionB.id]).toBeUndefined();
  });
});
