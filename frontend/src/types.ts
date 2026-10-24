export type Status = "PENDING" | "SENDING" | "SENT" | "FAILED" | "UNCERTAIN";
export interface DeliveryAttempt {
  attempt_number: number;
  started_at: string | null;
  finished_at: string | null;
  outcome: string | null;
  error_code: string | null;
  error_reason: string | null;
  reconciliation_action: string | null;
  reconciliation_note: string | null;
  reconciled_at: string | null;
}
export interface PreviousDelivery {
  participant_id: string;
  name: string;
  email: string;
  sent_at: string | null;
  smtp_message_id: string | null;
  filename: string | null;
}
export interface Participant {
  id: string;
  row_number: number;
  name: string;
  email: string;
  is_valid: boolean;
  is_excluded: boolean;
  validation_error: string | null;
  status: Status;
  filename: string | null;
  certificate_current: boolean;
  legibility_warning: string | null;
  generation_error: string | null;
  smtp_message_id: string | null;
  sent_at: string | null;
  updated_at: string | null;
  error_reason: string | null;
  delivery_reference: string;
  previous_delivery: PreviousDelivery | null;
  attempts: DeliveryAttempt[];
}
export interface Region {
  x: number;
  y: number;
  w: number;
  h: number;
  font_size: number;
  min_font_size: number;
  auto_fit: boolean;
  vertical_offset: number;
}
export interface Allowance {
  enabled: boolean;
  limit: number | null;
  used: number;
  remaining: number | null;
  successful: number;
  failed: number;
  uncertain: number;
  notice: string;
}
export interface SendProgress {
  total: number;
  processed: number;
  pending: number;
  sending: number;
  sent: number;
  failed: number;
  uncertain: number;
  percent: number;
  current_recipient: string | null;
  elapsed_seconds: number;
  eta_seconds: number;
  started_at: string | null;
  finished_at: string | null;
}
export interface GenerationProgress {
  job_id: string | null;
  status:
    "IDLE" | "RUNNING" | "COMPLETED" | "COMPLETED_WITH_ERRORS" | "INTERRUPTED";
  total: number;
  succeeded: number;
  failed: number;
  remaining: number;
  percent: number;
  current_name: string | null;
  started_at: string | null;
  finished_at: string | null;
}
export interface ImportCounts {
  total: number;
  valid: number;
  invalid: number;
  duplicates: number;
  preserved: number;
}
export interface Batch {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  template_path: boolean;
  font_path: boolean;
  font_name: string;
  uses_custom_font: boolean;
  sender_email: string | null;
  email_subject: string;
  email_body: string;
  is_paused: boolean;
  send_confirmed: boolean;
  region: Region;
  counts: Record<Status | "TOTAL", number>;
  ready_count: number;
  outdated_certificate_count: number;
  allowance: Allowance;
  progress: SendProgress;
  generation: GenerationProgress;
  participants: Participant[];
  import_counts: ImportCounts;
}
