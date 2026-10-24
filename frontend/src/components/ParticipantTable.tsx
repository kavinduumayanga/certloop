import { useEffect, useState } from "react";
import {
  Button,
  Checkbox,
  Chip,
  IconButton,
  Link,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import type { Participant, Status } from "../types";

const color: Record<
  Status,
  "default" | "primary" | "success" | "error" | "warning"
> = {
  PENDING: "default",
  SENDING: "primary",
  SENT: "success",
  FAILED: "error",
  UNCERTAIN: "warning",
};

function updatedLabel(participant: Participant) {
  if (participant.status === "PENDING" || !participant.updated_at) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(participant.updated_at));
}

function EditableParticipant({
  participant,
  onPatch,
}: {
  participant: Participant;
  onPatch: (id: string, data: Record<string, unknown>) => Promise<void>;
}) {
  const [name, setName] = useState(participant.name),
    [email, setEmail] = useState(participant.email),
    [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">(
      "idle",
    );
  const locked = ["SENT", "SENDING", "UNCERTAIN"].includes(participant.status);
  useEffect(() => {
    setName(participant.name);
    setEmail(participant.email);
  }, [participant.name, participant.email]);
  const save = async (field: "name" | "email") => {
    const value = field === "name" ? name : email;
    if (value === participant[field]) return;
    setSaveState("saving");
    try {
      await onPatch(participant.id, { [field]: value });
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  };
  const keySave = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.currentTarget.blur();
    }
  };
  return (
    <>
      <TableCell padding="checkbox">
        <Tooltip
          title={
            participant.is_excluded
              ? "Include participant"
              : "Exclude participant"
          }
        >
          <Checkbox
            checked={!participant.is_excluded}
            onChange={async (event) => {
              setSaveState("saving");
              try {
                await onPatch(participant.id, {
                  is_excluded: !event.target.checked,
                });
                setSaveState("saved");
              } catch {
                setSaveState("error");
              }
            }}
          />
        </Tooltip>
      </TableCell>
      <TableCell>
        <TextField
          variant="standard"
          value={name}
          disabled={locked}
          error={!name.trim()}
          onChange={(event) => {
            setName(event.target.value);
            setSaveState("idle");
          }}
          onBlur={() => void save("name")}
          onKeyDown={keySave}
          inputProps={{ "aria-label": `Name for ${participant.email}` }}
        />
      </TableCell>
      <TableCell>
        <TextField
          variant="standard"
          type="email"
          value={email}
          disabled={locked}
          error={!participant.is_valid}
          onChange={(event) => {
            setEmail(event.target.value);
            setSaveState("idle");
          }}
          onBlur={() => void save("email")}
          onKeyDown={keySave}
          inputProps={{
            "aria-label": `Email for ${participant.name || "participant"}`,
          }}
        />
      </TableCell>
      <TableCell>
        <Stack spacing={0.5} alignItems="flex-start">
          {participant.is_excluded ? (
            <Chip size="small" label="Excluded" />
          ) : participant.is_valid ? (
            <Chip
              size="small"
              color="success"
              variant="outlined"
              label="Valid"
            />
          ) : (
            <Chip size="small" color="error" label="Invalid" />
          )}
          {participant.validation_error && (
            <Typography variant="caption" color="error">
              {participant.validation_error}
            </Typography>
          )}
          {participant.previous_delivery && (
            <Chip
              size="small"
              color="warning"
              variant="outlined"
              label="Previously sent"
            />
          )}
          {saveState !== "idle" && (
            <Typography
              variant="caption"
              color={
                saveState === "error"
                  ? "error"
                  : saveState === "saved"
                    ? "success.main"
                    : "text.secondary"
              }
            >
              {saveState === "saving"
                ? "Saving…"
                : saveState === "saved"
                  ? "Saved"
                  : "Save failed"}
            </Typography>
          )}
        </Stack>
      </TableCell>
    </>
  );
}

export default function ParticipantTable({
  rows,
  onPatch,
  onReconcile,
}: {
  rows: Participant[];
  onPatch?: (id: string, data: Record<string, unknown>) => Promise<void>;
  onReconcile?: (
    id: string,
    action: "CONFIRM_SENT" | "CONFIRM_NOT_SENT",
  ) => void;
}) {
  return (
    <TableContainer
      component={Paper}
      variant="outlined"
      sx={{ maxHeight: 500 }}
    >
      <Table stickyHeader size="small">
        <TableHead>
          <TableRow>
            {onPatch && <TableCell padding="checkbox">Use</TableCell>}
            <TableCell>Participant</TableCell>
            <TableCell>Email</TableCell>
            <TableCell>Validation</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Updated</TableCell>
            <TableCell>Attempt</TableCell>
            {onReconcile && <TableCell>Reconcile</TableCell>}
            <TableCell align="right">PDF</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((participant) => (
            <TableRow key={participant.id} hover>
              {onPatch ? (
                <EditableParticipant
                  participant={participant}
                  onPatch={onPatch}
                />
              ) : (
                <>
                  <TableCell>{participant.name || <em>Missing</em>}</TableCell>
                  <TableCell>
                    {participant.email ? (
                      <Link href={`mailto:${participant.email}`}>
                        {participant.email}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    <Stack spacing={0.5} alignItems="flex-start">
                      {participant.is_valid ? (
                        <Chip
                          size="small"
                          color="success"
                          variant="outlined"
                          label="Valid"
                        />
                      ) : (
                        <Tooltip title={participant.validation_error || ""}>
                          <Chip size="small" color="error" label="Invalid" />
                        </Tooltip>
                      )}
                      {participant.previous_delivery && (
                        <Chip
                          size="small"
                          color="warning"
                          variant="outlined"
                          label="Previously sent"
                        />
                      )}
                      {participant.generation_error && (
                        <Tooltip title={participant.generation_error}>
                          <Chip
                            size="small"
                            color="error"
                            variant="outlined"
                            label="Generation failed"
                          />
                        </Tooltip>
                      )}
                    </Stack>
                  </TableCell>
                </>
              )}
              <TableCell>
                <Chip
                  size="small"
                  color={color[participant.status]}
                  label={participant.status}
                />
                {participant.error_reason && (
                  <Tooltip title={participant.error_reason}>
                    <span> ⓘ</span>
                  </Tooltip>
                )}
              </TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>
                {updatedLabel(participant)}
              </TableCell>
              <TableCell>
                {participant.attempts?.[0] ? (
                  <Tooltip
                    title={
                      participant.attempts[0].error_reason ||
                      `Delivery reference: ${participant.delivery_reference}`
                    }
                  >
                    <span>
                      #{participant.attempts[0].attempt_number}{" "}
                      {participant.attempts[0].outcome}
                    </span>
                  </Tooltip>
                ) : (
                  "—"
                )}
              </TableCell>
              {onReconcile && (
                <TableCell>
                  {participant.status === "UNCERTAIN" ? (
                    <Stack spacing={0.5} alignItems="flex-start">
                      <Button
                        size="small"
                        color="success"
                        onClick={() =>
                          onReconcile(participant.id, "CONFIRM_SENT")
                        }
                      >
                        Found in Sent
                      </Button>
                      <Button
                        size="small"
                        color="warning"
                        onClick={() =>
                          onReconcile(participant.id, "CONFIRM_NOT_SENT")
                        }
                      >
                        Not sent
                      </Button>
                      <Tooltip title="Use this reference when inspecting message details">
                        <code>{participant.delivery_reference.slice(-12)}</code>
                      </Tooltip>
                    </Stack>
                  ) : (
                    "—"
                  )}
                </TableCell>
              )}
              <TableCell align="right">
                {participant.filename && participant.certificate_current && (
                  <IconButton
                    aria-label={`Download ${participant.name}`}
                    component="a"
                    href={`/api/participants/${participant.id}/certificate`}
                  >
                    <DownloadIcon />
                  </IconButton>
                )}
                {participant.filename && !participant.certificate_current && (
                  <Tooltip title="Certificate styling changed; regenerate it">
                    <Chip size="small" color="warning" label="Outdated" />
                  </Tooltip>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
