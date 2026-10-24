import { Box, Card, CardContent, Typography } from "@mui/material";
import type { Batch } from "../types";

const items = [
  ["TOTAL", "Total recipients", "#E2E8F0"],
  ["PENDING", "Pending", "#94A3B8"],
  ["SENDING", "Sending", "#38BDF8"],
  ["SENT", "Sent", "#4ADE80"],
  ["FAILED", "Failed", "#F87171"],
  ["UNCERTAIN", "Uncertain", "#FBBF24"],
] as const;

export default function StatusCards({ batch }: { batch: Batch }) {
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(145px,1fr))", gap: 1.5 }}>
      {items.map(([key, label, color]) => (
        <Card key={key}>
          <CardContent sx={{ p: "18px !important" }}>
            <Typography variant="caption" color="text.secondary">{label}</Typography>
            <Typography variant="h4" sx={{ mt: 0.4, color }}>{batch.counts[key] ?? 0}</Typography>
            <Box sx={{ width: 28, height: 3, borderRadius: 999, mt: 1, bgcolor: color, opacity: 0.7 }} />
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}
