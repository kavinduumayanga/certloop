import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";
import {
  Box,
  Button,
  FormControlLabel,
  IconButton,
  InputAdornment,
  Slider,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import type { Region } from "../types";

interface NumberControlProps {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  slider?: boolean;
  error?: boolean;
  helperText?: string;
}

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, Math.round(value)));

function NumberControl({
  label,
  value,
  min,
  max,
  onChange,
  slider = false,
  error = false,
  helperText,
}: NumberControlProps) {
  const setValue = (next: number) => onChange(clamp(next, min, max));

  return (
    <Box className="name-style-control">
      <Typography variant="caption" fontWeight={700} color="text.secondary">
        {label}
      </Typography>
      <Stack direction="row" spacing={1} alignItems="center">
        {slider && (
          <Slider
            aria-label={`${label} slider`}
            value={value}
            min={min}
            max={max}
            step={1}
            onChange={(_, next) => setValue(next as number)}
            valueLabelDisplay="auto"
            valueLabelFormat={(next) => `${next}px`}
          />
        )}
        <TextField
          type="number"
          size="small"
          className="compact-number-input"
          value={value}
          error={error}
          helperText={helperText}
          inputProps={{ min, max, step: 1, "aria-label": `${label} value` }}
          InputProps={{
            endAdornment: <InputAdornment position="end">px</InputAdornment>,
          }}
          onChange={(event) => setValue(Number(event.target.value) || 0)}
        />
        <Stack direction="row" className="number-stepper" aria-label={`${label} controls`}>
          <Tooltip title={`Decrease ${label.toLowerCase()}`}>
            <span>
              <IconButton
                size="small"
                aria-label={`Decrease ${label.toLowerCase()}`}
                disabled={value <= min}
                onClick={() => setValue(value - 1)}
              >
                <RemoveIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={`Increase ${label.toLowerCase()}`}>
            <span>
              <IconButton
                size="small"
                aria-label={`Increase ${label.toLowerCase()}`}
                disabled={value >= max}
                onClick={() => setValue(value + 1)}
              >
                <AddIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Stack>
    </Box>
  );
}

interface NameStylingControlsProps {
  region: Region;
  dirty: boolean;
  saving: boolean;
  renderedFontSize: number;
  previewWarning: boolean;
  onChange: (partial: Partial<Region>) => void;
  onSave: () => void;
}

export default function NameStylingControls({
  region,
  dirty,
  saving,
  renderedFontSize,
  previewWarning,
  onChange,
  onSave,
}: NameStylingControlsProps) {
  const invalidMinimum = region.min_font_size > region.font_size;

  return (
    <Box component="section" className="name-styling-panel">
      <Stack
        direction={{ xs: "column", sm: "row" }}
        alignItems={{ sm: "center" }}
        justifyContent="space-between"
        spacing={1}
      >
        <Box>
          <Typography variant="h6">Name Styling</Typography>
        </Box>
        {renderedFontSize > 0 && (
          <Box className="effective-size" aria-live="polite">
            <Typography variant="caption" color="text.secondary">
              Effective rendered size
            </Typography>
            <Typography
              variant="subtitle2"
              color={previewWarning ? "warning.main" : "secondary.main"}
            >
              {renderedFontSize}px
            </Typography>
          </Box>
        )}
      </Stack>

      <Box className="name-styling-grid">
        <NumberControl
          label="Font Size"
          value={region.font_size}
          min={8}
          max={1000}
          slider
          onChange={(font_size) => onChange({ font_size })}
        />
        <NumberControl
          label="Minimum Font Size"
          value={region.min_font_size}
          min={8}
          max={500}
          error={invalidMinimum}
          helperText={
            invalidMinimum ? "Must not exceed the font size" : undefined
          }
          onChange={(min_font_size) => onChange({ min_font_size })}
        />
        <NumberControl
          label="Vertical Offset"
          value={region.vertical_offset}
          min={-1000}
          max={1000}
          slider
          onChange={(vertical_offset) => onChange({ vertical_offset })}
        />
        <Box className="auto-fit-control">
          <FormControlLabel
            control={
              <Switch
                checked={region.auto_fit}
                onChange={(event) =>
                  onChange({ auto_fit: event.target.checked })
                }
              />
            }
            label="Auto-fit Long Names"
          />
        </Box>
      </Box>

      <Stack
        direction={{ xs: "column", sm: "row" }}
        alignItems={{ xs: "flex-start", sm: "center" }}
        justifyContent="space-between"
        spacing={1.5}
        className="name-styling-actions"
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <Box
            className={`save-state-dot ${dirty ? "is-dirty" : ""}`}
            aria-hidden="true"
          />
          <Typography
            variant="caption"
            color={dirty ? "warning.main" : "text.secondary"}
          >
            {dirty ? "Unsaved changes" : "Placement is saved"}
          </Typography>
        </Stack>
        <Button
          size="small"
          variant="contained"
          disabled={!dirty || invalidMinimum || saving}
          onClick={onSave}
          sx={{ alignSelf: { xs: "stretch", sm: "auto" } }}
        >
          {saving ? "Saving…" : "Save Placement"}
        </Button>
      </Stack>
    </Box>
  );
}
