import type { Batch, Region } from "./types";
const base = "/api";
export interface ColumnMappingDetail {
  code: "column_mapping_required";
  message: string;
  headers: string[];
  detected?: { name: string | null; email: string | null };
}
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (
    detail &&
    typeof detail === "object" &&
    "message" in detail &&
    typeof detail.message === "string"
  )
    return detail.message;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String(item.msg)
          : "",
      )
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return `The request could not be completed (${status}). Please check the file and try again.`;
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(base + path, init);
  if (!response.ok) {
    let detail: unknown;
    try {
      const data = await response.json();
      detail = data.detail;
    } catch {}
    throw new ApiError(
      response.status,
      detail,
      errorMessage(detail, response.status),
    );
  }
  return response.json() as Promise<T>;
}
async function imageRequest(path: string, init?: RequestInit) {
  const response = await fetch(base + path, init);
  if (!response.ok) {
    let detail: unknown;
    try {
      const data = await response.json();
      detail = data.detail;
    } catch {}
    throw new ApiError(
      response.status,
      detail,
      errorMessage(detail, response.status),
    );
  }
  return {
    blob: await response.blob(),
    actualFontSize: Number(response.headers.get("X-Actual-Font-Size") || 0),
    warning: response.headers.get("X-Legibility-Warning") === "1",
  };
}
const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const api = {
  createBatch: (name: string) =>
    request<Batch>("/batches", json("POST", { name })),
  listBatches: () => request<Batch[]>("/batches"),
  getBatch: (id: string) => request<Batch>(`/batches/${id}`),
  upload: (id: string, kind: "template" | "font", file: File) => {
    const f = new FormData();
    f.append("file", file);
    return request<Batch>(`/batches/${id}/${kind}`, {
      method: "POST",
      body: f,
    });
  },
  importCsv: (
    id: string,
    file: File,
    nameColumn?: string,
    emailColumn?: string,
    confirmReplace = false,
  ) => {
    const f = new FormData();
    f.append("file", file);
    if (nameColumn) f.append("name_column", nameColumn);
    if (emailColumn) f.append("email_column", emailColumn);
    if (confirmReplace) f.append("confirm_replace", "true");
    return request<Batch>(`/batches/${id}/participants/import`, {
      method: "POST",
      body: f,
    });
  },
  updateParticipant: (id: string, data: unknown) =>
    request<Batch>(`/participants/${id}`, json("PATCH", data)),
  updateRegion: (id: string, region: Region) =>
    request<Batch>(`/batches/${id}/region`, json("PUT", region)),
  renderPreview: (
    id: string,
    participant_id: string,
    region: Region,
    signal?: AbortSignal,
  ) =>
    imageRequest(`/batches/${id}/render-preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ participant_id, ...region }),
      signal,
    }),
  generate: (id: string) =>
    request<{ started: boolean; total: number }>(`/batches/${id}/generate`, {
      method: "POST",
    }),
  configureEmail: (id: string, data: unknown) =>
    request<Batch>(`/batches/${id}/email`, json("PUT", data)),
  smtpStatus: () =>
    request<{
      configured: boolean;
      sender_email: string | null;
      aliases: string[];
      host: string;
      port: number;
    }>("/smtp/status"),
  send: (id: string, confirmation: string) =>
    request(`/batches/${id}/send`, json("POST", { confirmation })),
  reconcile: (
    id: string,
    action: "CONFIRM_SENT" | "CONFIRM_NOT_SENT",
    note = "",
  ) =>
    request<Batch>(
      `/participants/${id}/reconcile`,
      json("POST", {
        action,
        note,
        confirmation:
          action === "CONFIRM_SENT" ? "CONFIRM SENT" : "CONFIRM NOT SENT",
      }),
    ),
  action: (id: string, action: "pause" | "resume" | "retry-failed") =>
    request(`/batches/${id}/${action}`, { method: "POST" }),
};
