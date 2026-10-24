import { useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import WorkspacesOutlinedIcon from "@mui/icons-material/WorkspacesOutlined";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type { Batch } from "../types";

function sessionLabel(session: Batch) {
  const created = session.created_at
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(session.created_at))
    : "";
  return `${session.name}${created ? ` · ${created}` : ""}`;
}

interface Props {
  sessions: Batch[];
  current: Batch;
  onCreate: (name: string) => Promise<void>;
  onSelect: (id: string) => void;
  busy: boolean;
}

export default function SessionControls({ sessions, current, onCreate, onSelect, busy }: Props) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const cleanName = name.trim().replace(/\s+/g, " ");
  const clientError = !cleanName
    ? "Session name is required"
    : cleanName.length > 100
      ? "Session name must be 100 characters or fewer"
      : "";

  const close = () => {
    if (creating) return;
    setOpen(false);
    setName("");
    setError("");
  };
  const create = async () => {
    if (clientError) {
      setError(clientError);
      return;
    }
    setCreating(true);
    setError("");
    try {
      await onCreate(cleanName);
      setOpen(false);
      setName("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The session could not be created");
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <Paper className="glass-surface" sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} gap={1.5}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <Box sx={{ width: 42, height: 42, display: "grid", placeItems: "center", borderRadius: 2.5, color: "secondary.main", bgcolor: "rgba(56,189,248,.08)" }}>
                <WorkspacesOutlinedIcon />
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Current session</Typography>
                <Typography fontWeight={750}>{current.name}</Typography>
              </Box>
            </Stack>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)} disabled={busy}>New Session</Button>
          </Stack>
          <TextField select size="small" label="Open a previous session" value={current.id} onChange={(event) => onSelect(event.target.value)} disabled={busy || sessions.length === 0} fullWidth>
            {sessions.map((session) => <MenuItem key={session.id} value={session.id}>{sessionLabel(session)}</MenuItem>)}
          </TextField>
          <Typography variant="caption" color="text.secondary">
            Participant lists, certificate settings, email configuration, and delivery progress stay isolated per session.
          </Typography>
        </Stack>
      </Paper>
      <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
        <DialogTitle>Create a new session</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Give this certificate workflow a unique, friendly name. CertLoop manages its internal ID automatically.
          </Typography>
          <TextField
            autoFocus
            fullWidth
            label="Session name"
            value={name}
            disabled={creating}
            error={Boolean(error || (clientError && name.length > 0))}
            helperText={error || (name.length > 0 ? clientError : "Up to 100 characters")}
            inputProps={{ maxLength: 101 }}
            onChange={(event) => { setName(event.target.value); setError(""); }}
            onKeyDown={(event) => { if (event.key === "Enter") void create(); }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={close} disabled={creating}>Cancel</Button>
          <Button variant="contained" onClick={() => void create()} disabled={creating || Boolean(clientError)}>{creating ? "Creating…" : "Create Session"}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
