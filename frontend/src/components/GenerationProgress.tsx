import {
  Alert,
  LinearProgress,
  Paper,
  Stack,
  Typography,
  Box,
} from "@mui/material";
import type { GenerationProgress as Progress } from "../types";

export default function GenerationProgress({
  progress,
}: {
  progress: Progress;
}) {
  if (progress.status === "IDLE" && !progress.total) return null;
  const running = progress.status === "RUNNING";
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1}>
        <Stack direction="row" justifyContent="space-between">
          <Typography fontWeight={700}>
            {running ? "Generating certificates…" : "Generation summary"}
          </Typography>
          <Typography fontWeight={700}>
            {Math.round(progress.percent)}%
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={progress.percent}
          sx={{ height: 10, borderRadius: 5 }}
        />
        {progress.current_name && (
          <Typography variant="body2">
            Current certificate: <b>{progress.current_name}</b>
          </Typography>
        )}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(135px,1fr))",
            gap: 1,
          }}
        >
          <Typography variant="body2">
            Total: <b>{progress.total}</b>
          </Typography>
          <Typography variant="body2">
            Generated: <b>{progress.succeeded}</b>
          </Typography>
          <Typography variant="body2">
            Failed: <b>{progress.failed}</b>
          </Typography>
          <Typography variant="body2">
            Remaining: <b>{progress.remaining}</b>
          </Typography>
        </Box>
        {!running && progress.status === "COMPLETED" && (
          <Alert severity="success">
            Generation completed successfully: {progress.succeeded} certificate
            {progress.succeeded === 1 ? "" : "s"} generated.
          </Alert>
        )}
        {!running && progress.status === "COMPLETED_WITH_ERRORS" && (
          <Alert severity="warning">
            Generation completed with {progress.failed} failure
            {progress.failed === 1 ? "" : "s"}. Review the participant list for
            details.
          </Alert>
        )}
        {progress.status === "INTERRUPTED" && (
          <Alert severity="error">
            Generation was interrupted by a backend restart. Start generation
            again for the remaining certificates.
          </Alert>
        )}
      </Stack>
    </Paper>
  );
}
