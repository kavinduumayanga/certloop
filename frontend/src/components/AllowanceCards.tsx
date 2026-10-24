import { Alert, Box, Paper, Typography } from "@mui/material";
import type { Allowance } from "../types";

const items: [
  keyof Pick<Allowance, "used" | "successful" | "failed" | "uncertain">,
  string,
  string,
][] = [
  ["used", "Counted activity (24h)", "#16697a"],
  ["successful", "Successful sends", "#14866d"],
  ["failed", "Failed attempts", "#c2413b"],
  ["uncertain", "Uncertain attempts", "#b7791f"],
];

export default function AllowanceCards({
  allowance,
}: {
  allowance: Allowance;
}) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Application sending activity · rolling 24 hours
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
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Typography variant="caption" color="text.secondary">
              Configured app cap remaining
            </Typography>
            <Typography variant="h5" sx={{ color: "#132238" }}>
              {allowance.remaining} / {allowance.limit}
            </Typography>
          </Paper>
        )}
        {items.map(([key, label, color]) => (
          <Paper variant="outlined" key={key} sx={{ p: 1.5 }}>
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
