import { useMemo, useState } from "react";
import {
  Box,
  Chip,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type { Batch } from "../types";
import ParticipantTable from "./ParticipantTable";

export default function ImportSummary({
  batch,
  onPatch,
}: {
  batch: Batch;
  onPatch: (id: string, data: Record<string, unknown>) => Promise<void>;
}) {
  const [filter, setFilter] = useState<"ALL" | "INVALID" | "DUPLICATE">("ALL"),
    [search, setSearch] = useState("");
  const counts = batch.import_counts;
  const rows = useMemo(
    () =>
      batch.participants.filter((participant) => {
        const matchesFilter =
          filter === "ALL" ||
          (filter === "INVALID" && !participant.is_valid) ||
          (filter === "DUPLICATE" &&
            Boolean(participant.validation_error?.includes("Duplicate email")));
        return (
          matchesFilter &&
          `${participant.name} ${participant.email} ${participant.validation_error || ""}`
            .toLowerCase()
            .includes(search.toLowerCase())
        );
      }),
    [batch.participants, filter, search],
  );
  return (
    <Stack spacing={2}>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))",
          gap: 1.5,
        }}
      >
        {[
          ["Total imported", counts.total, "default"],
          ["Valid", counts.valid, "success"],
          ["Invalid", counts.invalid, "error"],
          ["Duplicates", counts.duplicates, "warning"],
        ].map(([label, value, color]) => (
          <Paper variant="outlined" key={String(label)} sx={{ p: 2, bgcolor: "rgba(2,6,23,.28)" }}>
            <Typography variant="caption" color="text.secondary">
              {label}
            </Typography>
            <Typography variant="h4" sx={{ my: 0.5 }}>{value}</Typography>
            <Chip
              size="small"
              color={color as "default" | "success" | "error" | "warning"}
              label={label}
            />
          </Paper>
        ))}
      </Box>
      <Box>
        <Typography variant="h6">Participant validation</Typography>
        <Typography variant="body2" color="text.secondary">
          Invalid and duplicate rows stay excluded from generation and sending
          until corrected. Edits save on blur or Enter and the entire import is
          revalidated automatically.
        </Typography>
      </Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
        <TextField
          size="small"
          label="Search participants or errors"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ flex: 1 }}
        />
        <TextField
          size="small"
          select
          label="Show"
          value={filter}
          onChange={(event) => setFilter(event.target.value as typeof filter)}
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="ALL">All participants</MenuItem>
          <MenuItem value="INVALID">Invalid only</MenuItem>
          <MenuItem value="DUPLICATE">Duplicates only</MenuItem>
        </TextField>
      </Stack>
      <ParticipantTable rows={rows} onPatch={onPatch} />
    </Stack>
  );
}
