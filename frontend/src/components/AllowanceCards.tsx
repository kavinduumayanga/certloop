import { Alert, Box, Paper, Typography } from "@mui/material";
import type { Allowance } from "../types";

const items: [
  keyof Pick<Allowance, "used" | "successful" | "failed" | "uncertain">,
  string,
  string,
][] = [
  ["used", "Counted activity (24h)", "#38BDF8"],
  ["successful", "Successful sends", "#4ADE80"],
  ["failed", "Failed attempts", "#F87171"],
  ["uncertain", "Uncertain attempts", "#FBBF24"],
];

export default function AllowanceCards({
  allowance,
}: {
  allowance: Allowance;
}) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Sending activity · rolling 24 hours
      </Typography>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))",
          gap: 1.5,
          mb: 1.5,
        }}
      >
        {allowance.enabled && (
          <Paper variant="outlined" sx={{ p: 2, bgcolor: "rgba(2,6,23,.28)" }}>
            <Typography variant="caption" color="text.secondary">
              Configured app cap remaining
            </Typography>
            <Typography variant="h5" color="secondary.main">
              {allowance.remaining} / {allowance.limit}
            </Typography>
          </Paper>
        )}
        {items.map(([key, label, color]) => (
          <Paper variant="outlined" key={key} sx={{ p: 2, bgcolor: "rgba(2,6,23,.28)" }}>
            <Typography variant="caption" color="text.secondary">
              {label}
            </Typography>
            <Typography variant="h5" sx={{ color }}>
              {allowance[key]}
            </Typography>
          </Paper>
        ))}
      </Box>
      <Alert severity="info">{allowance.notice}</Alert>
    </Box>
  );
}
