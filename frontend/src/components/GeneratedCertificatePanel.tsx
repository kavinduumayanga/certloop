import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import RefreshIcon from "@mui/icons-material/Refresh";
import type { Participant } from "../types";

interface GeneratedCertificatePanelProps {
  participants: Participant[];
  selectedId: string;
  generationRunning: boolean;
  regeneratingId: string | null;
  onSelect: (participantId: string) => void;
  onRegenerate: (participantId: string) => void;
}

export default function GeneratedCertificatePanel({
  participants,
  selectedId,
  generationRunning,
  regeneratingId,
  onSelect,
  onRegenerate,
}: GeneratedCertificatePanelProps) {
  const selected = participants.find((row) => row.id === selectedId) ?? null;
  const generatedCount = participants.filter((row) => row.filename).length;
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState(false);
  const previewVersion = selected?.updated_at ?? selected?.filename ?? "latest";

  useEffect(() => {
    setPreviewError(false);
    setPreviewLoading(Boolean(selected?.filename));
  }, [selected?.id, selected?.filename, previewVersion]);

  if (!participants.length) {
    return (
      <Alert severity="info">
        Import participants before generating certificate previews.
      </Alert>
    );
  }

  const canRegenerate = Boolean(
    selected?.is_valid && !selected.is_excluded && !generationRunning,
  );

  return (
    <Box className="generated-certificate-panel">
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={1.25}
        alignItems={{ md: "center" }}
      >
        <Autocomplete
          size="small"
          fullWidth
          options={participants}
          value={selected}
          getOptionLabel={(option) => `${option.name} · ${option.email}`}
          isOptionEqualToValue={(option, value) => option.id === value.id}
          onChange={(_, participant) => onSelect(participant?.id ?? "")}
          renderOption={({ key, ...props }, option) => (
            <li key={key} {...props}>
              <Box minWidth={0} flex={1}>
                <Typography variant="body2" fontWeight={650} noWrap>
                  {option.name}
                </Typography>
                <Typography variant="caption" color="text.secondary" noWrap>
                  {option.email}
                </Typography>
              </Box>
              <Chip
                size="small"
                color={
                  option.certificate_current
                    ? "success"
                    : option.filename
                      ? "warning"
                      : "default"
                }
                variant="outlined"
                label={
                  option.certificate_current
                    ? "Generated"
                    : option.filename
                      ? "Outdated"
                      : "Not generated"
                }
              />
            </li>
          )}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Participant certificate"
              placeholder="Search by name or email"
            />
          )}
          sx={{ minWidth: { md: 360 } }}
        />
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1}
          flexShrink={0}
        >
          <Button
            component="a"
            size="small"
            variant="outlined"
            startIcon={<DownloadIcon />}
            href={
              selected?.filename
                ? `/api/participants/${selected.id}/certificate?v=${encodeURIComponent(previewVersion)}`
                : undefined
            }
            disabled={!selected?.filename}
            sx={{ width: { xs: "100%", sm: "auto" } }}
          >
            Download
          </Button>
          <Button
            size="small"
            variant="contained"
            startIcon={
              regeneratingId === selected?.id ? (
                <CircularProgress size={15} color="inherit" />
              ) : (
                <RefreshIcon />
              )
            }
            disabled={!canRegenerate || Boolean(regeneratingId)}
            onClick={() => selected && onRegenerate(selected.id)}
            sx={{ width: { xs: "100%", sm: "auto" } }}
          >
            Regenerate Certificate
          </Button>
        </Stack>
      </Stack>

      {!generatedCount && (
        <Alert severity="info" sx={{ mt: 1.5 }}>
          No certificates have been generated yet. Select a valid participant
          to generate one, or use Generate All.
        </Alert>
      )}
      {selected?.filename && !selected.certificate_current && (
        <Alert severity="warning" sx={{ mt: 1.5 }}>
          This preview is from an older template or placement configuration.
          Regenerate it to create the latest version.
        </Alert>
      )}
      {selected?.generation_error && (
        <Alert severity="error" sx={{ mt: 1.5 }}>
          {selected.generation_error}
        </Alert>
      )}

      <Box className="generated-preview-frame">
        {selected?.filename ? (
          <>
            {previewLoading && !previewError && (
              <Box className="generated-preview-state">
                <CircularProgress size={28} />
              </Box>
            )}
            {previewError ? (
              <Box className="generated-preview-state">
                <Typography color="error.main">
                  The certificate preview could not be loaded.
                </Typography>
              </Box>
            ) : (
              <img
                src={`/api/participants/${selected.id}/preview?v=${encodeURIComponent(previewVersion)}`}
                alt={`Generated certificate for ${selected.name}`}
                onLoad={() => setPreviewLoading(false)}
                onError={() => {
                  setPreviewLoading(false);
                  setPreviewError(true);
                }}
              />
            )}
          </>
        ) : (
          <Box className="generated-preview-state">
            <Typography color="text.secondary" textAlign="center">
              {selected
                ? `${selected.name} does not have a generated certificate yet.`
                : "Select a participant to preview their certificate."}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
