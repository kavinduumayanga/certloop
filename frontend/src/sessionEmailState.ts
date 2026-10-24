import type { Batch } from "./types";

export interface EmailDraft {
  sender_email: string;
  email_subject: string;
  email_body: string;
}

export type SessionEmailDrafts = Record<string, EmailDraft>;

export const emailDraftFromBatch = (
  batch: Pick<Batch, "sender_email" | "email_subject" | "email_body">,
): EmailDraft => ({
  sender_email: batch.sender_email ?? "",
  email_subject: batch.email_subject,
  email_body: batch.email_body,
});

export const setSessionEmailDraft = (
  drafts: SessionEmailDrafts,
  sessionId: string,
  draft: EmailDraft,
): SessionEmailDrafts => ({ ...drafts, [sessionId]: draft });

export const updateSessionEmailDraft = (
  drafts: SessionEmailDrafts,
  batch: Pick<Batch, "id" | "sender_email" | "email_subject" | "email_body">,
  partial: Partial<EmailDraft>,
): SessionEmailDrafts =>
  setSessionEmailDraft(drafts, batch.id, {
    ...(drafts[batch.id] ?? emailDraftFromBatch(batch)),
    ...partial,
  });
