import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  AppBar,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  Step,
  StepButton,
  Stepper,
  Switch,
  TextField,
  Toolbar,
  Typography,
} from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import EmailIcon from "@mui/icons-material/Email";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import DownloadIcon from "@mui/icons-material/Download";
import KeyboardArrowLeftIcon from "@mui/icons-material/KeyboardArrowLeft";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
import { Rnd } from "react-rnd";
import { api, ApiError } from "./api";
import type { Batch, Region, Status } from "./types";
import ParticipantTable from "./components/ParticipantTable";
import AllowanceCards from "./components/AllowanceCards";
import ImportSummary from "./components/ImportSummary";
import GenerationProgress from "./components/GenerationProgress";
import SessionControls from "./components/SessionControls";
import StatusCards from "./components/StatusCards";
import BrandMark from "./components/BrandMark";
import {
  DEFAULT_EMAIL_BODY,
  DEFAULT_EMAIL_SUBJECT,
  renderEmailTemplate,
} from "./emailTemplate";
import {
  emailDraftFromBatch,
  setSessionEmailDraft,
  updateSessionEmailDraft,
  type SessionEmailDrafts,
} from "./sessionEmailState";

const steps = [
  "Import Participants",
  "Template & Font",
  "Generate & Preview",
  "Configure Email",
  "Send Certificates",
];
const defaultRegion: Region = {
  x: 0.2,
  y: 0.45,
  w: 0.6,
  h: 0.12,
  font_size: 110,
  min_font_size: 38,
  auto_fit: true,
  vertical_offset: 0,
};
const duration = (seconds: number) => {
  const minutes = Math.floor(seconds / 60),
    remainder = seconds % 60;
  return minutes ? `${minutes}m ${remainder}s` : `${remainder}s`;
};
function UploadButton({
  label,
  accept,
  onFile,
}: {
  label: string;
  accept: string;
  onFile: (f: File) => void;
}) {
  return (
    <Button
      component="label"
      variant="outlined"
      className="upload-zone"
      fullWidth
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
    >
      <Stack alignItems="center" spacing={1}>
        <Box
          sx={{
            width: 42,
            height: 42,
            display: "grid",
            placeItems: "center",
            borderRadius: 2.5,
            color: "secondary.main",
            bgcolor: "rgba(56,189,248,.09)",
          }}
        >
          <CloudUploadIcon />
        </Box>
        <Box>
          <Typography fontWeight={700}>{label}</Typography>
          <Typography variant="caption" color="text.secondary">
            Drop a file here or browse your device
          </Typography>
        </Box>
      </Stack>
      <input
        hidden
        type="file"
        accept={accept}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.currentTarget.value = "";
        }}
      />
    </Button>
  );
}

export default function App() {
  const [batch, setBatch] = useState<Batch | null>(null),
    [sessions, setSessions] = useState<Batch[]>([]),
    [step, setStep] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState<"ALL" | Status>("ALL"),
    [confirmOpen, setConfirmOpen] = useState(false),
    [confirm, setConfirm] = useState(""),
    [retryOpen, setRetryOpen] = useState(false),
    [identity, setIdentity] = useState("");
  const [emailDrafts, setEmailDrafts] = useState<SessionEmailDrafts>({});
  const [emailDirtyBySession, setEmailDirtyBySession] = useState<
    Record<string, boolean>
  >({});
  const emailDraft = batch
    ? (emailDrafts[batch.id] ?? emailDraftFromBatch(batch))
    : null;
  const emailDirty = batch
    ? Boolean(emailDirtyBySession[batch.id])
    : false;
  const [csvMapping, setCsvMapping] = useState<{
      file: File;
      headers: string[];
    } | null>(null),
    [nameColumn, setNameColumn] = useState(""),
    [emailColumn, setEmailColumn] = useState("");
  const [draftRegion, setDraftRegion] = useState<Region | null>(null),
    [regionDirty, setRegionDirty] = useState(false),
    [selectedPreviewId, setSelectedPreviewId] = useState("");
  const [previewUrl, setPreviewUrl] = useState(""),
    [previewWarning, setPreviewWarning] = useState(false),
    [previewFontSize, setPreviewFontSize] = useState(0),
    [previewRendering, setPreviewRendering] = useState(false);
  const [previewSize, setPreviewSize] = useState({ width: 0, height: 0 });
  const [leaveOpen, setLeaveOpen] = useState(false),
    [pendingStep, setPendingStep] = useState<number | null>(null);
  const previewRef = useRef<HTMLDivElement>(null),
    bootstrapStarted = useRef(false),
    activeSessionId = useRef("");
  const run = async <T,>(fn: () => Promise<T>, done?: (value: T) => void) => {
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      done?.(result);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setBusy(false);
    }
  };
  const activateSession = (selected: Batch, returnToImport = false) => {
    activeSessionId.current = selected.id;
    localStorage.setItem("certificateBatchId", selected.id);
    setBatch(selected);
    setEmailDirtyBySession((current) => ({
      ...current,
      [selected.id]: false,
    }));
    setEmailDrafts((current) =>
      setSessionEmailDraft(
        current,
        selected.id,
        emailDraftFromBatch(selected),
      ),
    );
    setDraftRegion(selected.region);
    setRegionDirty(false);
    setCsvMapping(null);
    setNameColumn("");
    setEmailColumn("");
    setSearch("");
    setFilter("ALL");
    if (returnToImport) setStep(0);
  };
  const bootstrap = () => {
    return run(
      async () => {
        const available = await api.listBatches();
        const savedId = localStorage.getItem("certificateBatchId");
        const selectedSummary =
          available.find((session) => session.id === savedId) ?? available[0];
        const selected = selectedSummary
          ? await api.getBatch(selectedSummary.id)
          : await api.createBatch("Workshop certificates");
        return {
          selected,
          available: selectedSummary ? available : [selected],
        };
      },
      ({ selected, available }) => {
        setSessions(available);
        activateSession(selected);
      },
    );
  };
  useEffect(() => {
    if (bootstrapStarted.current) return;
    bootstrapStarted.current = true;
    void bootstrap();
  }, []);
  useEffect(() => {
    if (!batch) return;
    const sessionId = batch.id;
    const source = new EventSource(`/api/batches/${sessionId}/events`);
    source.onmessage = (e) => {
      const update = JSON.parse(e.data) as Batch;
      if (activeSessionId.current === sessionId && update.id === sessionId)
        setBatch(update);
    };
    return () => source.close();
  }, [batch?.id]);
  useEffect(() => {
    api
      .smtpStatus()
      .then((status) =>
        setIdentity(status.configured ? (status.sender_email ?? "") : ""),
      )
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (batch && !emailDirty) {
      setEmailDrafts((current) =>
        setSessionEmailDraft(current, batch.id, emailDraftFromBatch(batch)),
      );
    }
  }, [
    batch?.id,
    batch?.sender_email,
    batch?.email_subject,
    batch?.email_body,
    emailDirty,
  ]);
  const valid =
    batch?.participants.filter((p) => p.is_valid && !p.is_excluded) ?? [];
  const region = draftRegion ?? batch?.region ?? defaultRegion;
  useEffect(() => {
    if (batch && !regionDirty) setDraftRegion(batch.region);
  }, [
    batch?.region.x,
    batch?.region.y,
    batch?.region.w,
    batch?.region.h,
    batch?.region.font_size,
    batch?.region.min_font_size,
    batch?.region.auto_fit,
    batch?.region.vertical_offset,
    regionDirty,
  ]);
  useEffect(() => {
    if (valid.length && !valid.some((p) => p.id === selectedPreviewId))
      setSelectedPreviewId(valid[0].id);
    if (!valid.length) setSelectedPreviewId("");
  }, [batch?.participants, selectedPreviewId]);
  useEffect(() => {
    if (
      !batch?.template_path ||
      !batch.font_path ||
      !selectedPreviewId ||
      region.min_font_size > region.font_size
    ) {
      setPreviewUrl("");
      setPreviewWarning(false);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setPreviewRendering(true);
      try {
        const result = await api.renderPreview(
          batch.id,
          selectedPreviewId,
          region,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        setPreviewUrl(URL.createObjectURL(result.blob));
        setPreviewFontSize(result.actualFontSize);
        setPreviewWarning(result.warning);
      } catch (cause) {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error
              ? cause.message
              : "Live preview could not be rendered.",
          );
      } finally {
        if (!controller.signal.aborted) setPreviewRendering(false);
      }
    }, 220);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    batch?.id,
    batch?.template_path,
    batch?.font_path,
    selectedPreviewId,
    region.x,
    region.y,
    region.w,
    region.h,
    region.font_size,
    region.min_font_size,
    region.auto_fit,
    region.vertical_offset,
  ]);
  useEffect(() => {
    const element = previewRef.current;
    if (step !== 1 || !element) return;
    const update = () =>
      setPreviewSize({
        width: element.clientWidth,
        height: element.clientHeight,
      });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [step, batch?.template_path]);
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (regionDirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [regionDirty]);
  const shown = useMemo(
    () =>
      batch?.participants.filter(
        (p) =>
          (filter === "ALL" || p.status === filter) &&
          `${p.name} ${p.email}`.toLowerCase().includes(search.toLowerCase()),
      ) ?? [],
    [batch, search, filter],
  );
  if (!batch)
    return (
      <Box minHeight="100vh" display="grid" sx={{ placeItems: "center", p: 3 }}>
        {error ? (
          <Paper variant="outlined" sx={{ p: 3, maxWidth: 520 }}>
            <Stack spacing={2}>
              <Alert severity="error">
                Could not reach the certificate backend: {error}
              </Alert>
              <Typography color="text.secondary">
                Start FastAPI on port 8000, then retry.
              </Typography>
              <Button variant="contained" onClick={() => void bootstrap()}>
                Retry connection
              </Button>
            </Stack>
          </Paper>
        ) : (
          <Stack alignItems="center" spacing={2} sx={{ width: "100%", px: 2, textAlign: "center" }}>
            <BrandMark size={82} priority />
            <CircularProgress size={26} />
            <Typography variant="h6">CertLoop</Typography>
            <Typography color="text.secondary" sx={{ maxWidth: "100%" }}>
              Connecting to the local certificate service…
            </Typography>
          </Stack>
        )}
      </Box>
    );
  const setB = (b: Batch) => setBatch(b);
  const createNewSession = async (name: string) => {
    setBusy(true);
    setError("");
    try {
      const created = await api.createBatch(name);
      setSessions((current) => [
        created,
        ...current.filter((session) => session.id !== created.id),
      ]);
      activateSession(created, true);
      setNotice("New session created");
    } finally {
      setBusy(false);
    }
  };
  const selectSession = (sessionId: string) => {
    if (sessionId === batch.id) return;
    void run(
      () => api.getBatch(sessionId),
      (selected) => {
        activateSession(selected, true);
        setNotice(`Opened ${selected.name}`);
      },
    );
  };
  const importParticipants = async (
    file: File,
    name?: string,
    email?: string,
    confirmReplace = false,
  ) => {
    setBusy(true);
    setError("");
    try {
      const imported = await api.importCsv(
        batch.id,
        file,
        name,
        email,
        confirmReplace,
      );
      setB(imported);
      setCsvMapping(null);
      setNameColumn("");
      setEmailColumn("");
      const counts = imported.import_counts;
      setNotice(
        counts
          ? `${counts.total} rows imported: ${counts.valid} valid, ${counts.invalid} invalid${counts.duplicates ? ` (${counts.duplicates} duplicate${counts.duplicates === 1 ? "" : "s"})` : ""}`
          : `${imported.participants.length} rows imported`,
      );
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        cause.detail &&
        typeof cause.detail === "object" &&
        "code" in cause.detail &&
        cause.detail.code === "replace_confirmation_required"
      ) {
        const message =
          "This session already has generated certificates or delivery activity. Replacing the active CSV will archive those participant rows and reset this session's live job progress, while preserving all delivery history. Continue?";
        if (window.confirm(message))
          await importParticipants(file, name, email, true);
      } else if (
        cause instanceof ApiError &&
        cause.detail &&
        typeof cause.detail === "object" &&
        "code" in cause.detail &&
        cause.detail.code === "column_mapping_required" &&
        "headers" in cause.detail &&
        Array.isArray(cause.detail.headers)
      ) {
        const detail = cause.detail as {
          message?: string;
          headers: string[];
          detected?: { name: string | null; email: string | null };
        };
        setCsvMapping({ file, headers: detail.headers });
        setNameColumn(detail.detected?.name ?? "");
        setEmailColumn(detail.detected?.email ?? "");
        setError(
          detail.message ?? "Choose the participant Name and Email columns.",
        );
      } else
        setError(
          cause instanceof Error
            ? cause.message
            : "The CSV could not be imported.",
        );
    } finally {
      setBusy(false);
    }
  };
  const updateRegion = (partial: Partial<Region>) => {
    setDraftRegion({ ...region, ...partial });
    setRegionDirty(true);
  };
  const saveRegion = () =>
    run(
      () => api.updateRegion(batch.id, region),
      (b) => {
        setB(b);
        setDraftRegion(b.region);
        setRegionDirty(false);
        setNotice("Name placement saved");
      },
    );
  const requestStep = (target: number) => {
    if (step === 1 && target !== 1 && regionDirty) {
      setPendingStep(target);
      setLeaveOpen(true);
    } else setStep(target);
  };
  const previewVariants = (() => {
    if (!valid.length) return [];
    const sorted = [...valid].sort((a, b) => a.name.length - b.name.length);
    return [
      sorted[0],
      sorted[Math.floor((sorted.length - 1) / 2)],
      sorted[sorted.length - 1],
    ].filter(
      (item, index, list) =>
        list.findIndex((other) => other.id === item.id) === index,
    );
  })();
  const leaveWithoutSaving = () => {
    setDraftRegion(batch.region);
    setRegionDirty(false);
    setLeaveOpen(false);
    if (pendingStep !== null) setStep(pendingStep);
    setPendingStep(null);
  };
  const saveAndLeave = () =>
    run(
      () => api.updateRegion(batch.id, region),
      (b) => {
        setB(b);
        setDraftRegion(b.region);
        setRegionDirty(false);
        setLeaveOpen(false);
        if (pendingStep !== null) setStep(pendingStep);
        setPendingStep(null);
        setNotice("Name placement saved");
      },
    );
  const pending = batch.counts.PENDING;
  const ready = batch.ready_count;
  const currentCertificate = valid.find((p) => p.certificate_current);
  const completed =
    batch.counts.SENT + batch.counts.FAILED + batch.counts.UNCERTAIN;
  const job = batch.progress;
  const progress = job.total
    ? job.percent
    : batch.counts.TOTAL
      ? (completed / batch.counts.TOTAL) * 100
      : 0;
  const pendingEligible = valid.filter((p) => p.status === "PENDING").length;
  const missingCurrentPdf = pendingEligible - ready;
  const invalidIncluded = batch.participants.filter(
    (p) => !p.is_valid && !p.is_excluded,
  ).length;
  const nonPending = valid.filter((p) => p.status !== "PENDING").length;
  const sendBlockedReasons = [
    batch.participants.length === 0 && "No participants have been imported",
    missingCurrentPdf > 0 &&
      `${missingCurrentPdf} pending eligible participant${missingCurrentPdf === 1 ? " is" : "s are"} missing a current PDF`,
    pendingEligible === 0 &&
      nonPending > 0 &&
      "All valid included participants already have non-pending statuses",
    pendingEligible === 0 &&
      valid.length === 0 &&
      batch.participants.length > 0 &&
      "No valid included participants are available",
    !batch.sender_email && "The sender email configuration has not been saved",
    !identity && "Gmail SMTP is not configured",
    batch.allowance.enabled &&
      batch.allowance.remaining !== null &&
      batch.allowance.remaining < 1 &&
      "The configured rolling 24-hour application cap is exhausted",
  ].filter(Boolean) as string[];
  const patchParticipant = async (
    id: string,
    data: Record<string, unknown>,
  ) => {
    try {
      const updated = await api.updateParticipant(id, data);
      setB(updated);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Participant changes could not be saved",
      );
      throw cause;
    }
  };
  const changeEmailDraft = (
    partial: Partial<NonNullable<typeof emailDraft>>,
  ) => {
    setEmailDrafts((current) =>
      updateSessionEmailDraft(current, batch, partial),
    );
    setEmailDirtyBySession((current) => ({
      ...current,
      [batch.id]: true,
    }));
  };
  const emailSave = () =>
    run(
      () =>
        api.configureEmail(batch.id, {
          sender_email: emailDraft?.sender_email || identity,
          subject: emailDraft?.email_subject ?? batch.email_subject,
          body: emailDraft?.email_body ?? batch.email_body,
        }),
      (b) => {
        setB(b);
        setEmailDrafts((current) =>
          setSessionEmailDraft(current, b.id, emailDraftFromBatch(b)),
        );
        setEmailDirtyBySession((current) => ({
          ...current,
          [b.id]: false,
        }));
        setNotice("Email configuration saved");
      },
    );
  const restoreDefaultEmailTemplate = () => {
    changeEmailDraft({
      email_subject: DEFAULT_EMAIL_SUBJECT,
      email_body: DEFAULT_EMAIL_BODY,
    });
    setNotice("Default template restored. Save the email to keep it.");
  };
  const startSend = () =>
    run(
      () => api.send(batch.id, confirm),
      () => {
        setConfirmOpen(false);
        setNotice("Delivery worker started");
      },
    );
  const reconcile = (
    id: string,
    action: "CONFIRM_SENT" | "CONFIRM_NOT_SENT",
  ) => {
    const sent = action === "CONFIRM_SENT";
    const message = sent
      ? "Only continue after confirming this exact message exists in Gmail Sent. Mark it as Sent?"
      : "Only continue after confirming the message is not in Gmail Sent and was not received. Mark it Failed so it can be retried explicitly?";
    if (window.confirm(message))
      void run(
        () => api.reconcile(id, action),
        (b) => {
          setB(b);
          setNotice(
            sent
              ? "Submission reconciled as Sent"
              : "Submission reconciled as Failed",
          );
        },
      );
  };
  const emailPreviewName =
    batch.participants.find(
      (participant) => participant.is_valid && !participant.is_excluded,
    )?.name ?? "Participant Name";
  const emailPreviewSubject = renderEmailTemplate(
    emailDraft?.email_subject ?? batch.email_subject,
    emailPreviewName,
  );
  const emailPreviewBody = renderEmailTemplate(
    emailDraft?.email_body ?? batch.email_body,
    emailPreviewName,
  );
  const content = [
    <Stack spacing={3} key="import">
      <SessionControls
        sessions={sessions}
        current={batch}
        onCreate={createNewSession}
        onSelect={selectSession}
        busy={busy}
      />
      <Box>
        <Typography variant="h5">Bring in your participant list</Typography>
        <Typography color="text.secondary">
          Standard CSV and Google Forms exports are recognized automatically.
          Each successful CSV replaces the active list atomically while previous
          delivery records remain archived.
        </Typography>
      </Box>
      <UploadButton
        label="Choose participant CSV"
        accept=".csv,text/csv"
        onFile={(f) => void importParticipants(f)}
      />
      {csvMapping && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack spacing={2}>
            <Box>
              <Typography fontWeight={700}>
                Choose participant columns
              </Typography>
              <Typography variant="body2" color="text.secondary">
                The headings in {csvMapping.file.name} were not recognized
                automatically. Select the columns containing each participant's
                name and email.
              </Typography>
            </Box>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                select
                fullWidth
                label="Name column"
                value={nameColumn}
                onChange={(e) => setNameColumn(e.target.value)}
              >
                {csvMapping.headers.map((header) => (
                  <MenuItem key={`name-${header}`} value={header}>
                    {header || "(blank heading)"}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                fullWidth
                label="Email column"
                value={emailColumn}
                onChange={(e) => setEmailColumn(e.target.value)}
              >
                {csvMapping.headers.map((header) => (
                  <MenuItem key={`email-${header}`} value={header}>
                    {header || "(blank heading)"}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            <Box>
              <Button
                variant="contained"
                disabled={
                  !nameColumn || !emailColumn || nameColumn === emailColumn
                }
                onClick={() =>
                  void importParticipants(
                    csvMapping.file,
                    nameColumn,
                    emailColumn,
                  )
                }
              >
                Import with selected columns
              </Button>
            </Box>
          </Stack>
        </Paper>
      )}
      <Alert severity="info">
        Need an example?{" "}
        <a href="/samples/participants.csv" download>
          Use the sample CSV in the repository
        </a>
        . Invalid and duplicate rows remain visible but are excluded from
        generation and sending.
      </Alert>
      <ImportSummary batch={batch} onPatch={patchParticipant} />
    </Stack>,
    <Stack spacing={3} key="design">
      <Box>
        <Typography variant="h5">Position the real certificate name</Typography>
        <Typography color="text.secondary">
          This full-resolution preview is rendered by the same backend code used
          for generated PDFs. The dashed box is an editor guide only.
        </Typography>
      </Box>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
          gap: 2,
        }}
      >
        <UploadButton
          label={
            batch.template_path ? "Replace template" : "Upload PNG/JPG template"
          }
          accept="image/png,image/jpeg"
          onFile={(f) =>
            run(
              () => api.upload(batch.id, "template", f),
              (b) => {
                setB(b);
                setDraftRegion(b.region);
                setRegionDirty(false);
              },
            )
          }
        />
        <UploadButton
          label={
            batch.font_path ? "Replace font" : "Upload Citadel Script font"
          }
          accept=".ttf,.otf,font/ttf,font/otf"
          onFile={(f) => run(() => api.upload(batch.id, "font", f), setB)}
        />
      </Box>
      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
        {batch.template_path && <Chip color="success" variant="outlined" label="Template ready" />}
        {batch.font_path && <Chip color="success" variant="outlined" label="Exact font ready" />}
        {regionDirty && <Chip color="warning" variant="outlined" label="Unsaved placement" />}
      </Stack>
      <Autocomplete
        options={valid}
        value={valid.find((p) => p.id === selectedPreviewId) ?? null}
        getOptionLabel={(option) => `${option.name} · ${option.email}`}
        isOptionEqualToValue={(option, value) => option.id === value.id}
        onChange={(_, participant) =>
          setSelectedPreviewId(participant?.id ?? "")
        }
        renderInput={(params) => (
          <TextField
            {...params}
            label="Preview participant"
            placeholder="Search by name or email"
          />
        )}
      />
      {previewVariants.length > 0 && (
        <Stack
          direction="row"
          spacing={1}
          useFlexGap
          flexWrap="wrap"
          alignItems="center"
        >
          <Typography variant="body2" color="text.secondary">
            Quick checks:
          </Typography>
          {previewVariants.map((participant, index) => (
            <Button
              key={participant.id}
              size="small"
              variant={
                participant.id === selectedPreviewId ? "contained" : "outlined"
              }
              onClick={() => setSelectedPreviewId(participant.id)}
            >
              {index === 0
                ? "Short"
                : index === previewVariants.length - 1
                  ? "Longest"
                  : "Medium"}{" "}
              · {participant.name}
            </Button>
          ))}
        </Stack>
      )}
      <Box
        className={`preview-box ${batch.template_path ? "has-image" : ""}`}
        ref={previewRef}
      >
        {batch.template_path ? (
          <>
            <img
              src={previewUrl || `/api/batches/${batch.id}/template-file`}
              alt={
                previewUrl
                  ? "Live personalized certificate preview"
                  : "Certificate template"
              }
            />
            {previewRendering && (
              <Box className="preview-rendering">
                <CircularProgress size={30} />
              </Box>
            )}
            <Rnd
              className="name-region"
              bounds="parent"
              minWidth={24}
              minHeight={18}
              size={{
                width: `${region.w * 100}%`,
                height: `${region.h * 100}%`,
              }}
              position={{
                x: previewSize.width * region.x,
                y: previewSize.height * region.y,
              }}
              onDrag={(_, d) => {
                const el = previewRef.current;
                if (el)
                  updateRegion({
                    x: d.x / el.clientWidth,
                    y: d.y / el.clientHeight,
                  });
              }}
              onResize={(_, __, ref, ___, position) => {
                const el = previewRef.current;
                if (el)
                  updateRegion({
                    x: position.x / el.clientWidth,
                    y: position.y / el.clientHeight,
                    w: ref.offsetWidth / el.clientWidth,
                    h: ref.offsetHeight / el.clientHeight,
                  });
              }}
            />
          </>
        ) : (
          <Typography color="text.secondary">
            Upload a template to position the name area.
          </Typography>
        )}
      </Box>
      {batch.template_path && !batch.font_path && (
        <Alert severity="info">
          Upload the licensed Citadel Script font to render an exact
          personalized preview.
        </Alert>
      )}
      {previewWarning && (
        <Alert severity="warning">
          This name cannot fit inside the selected area at the configured
          minimum font size. Enlarge the box, reduce the minimum, or shorten the
          name.
        </Alert>
      )}
      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
        <Chip
          variant="outlined"
          label={`Requested size: ${region.font_size}px`}
        />
        {previewFontSize > 0 && (
          <Chip
            color={previewWarning ? "warning" : "success"}
            variant="outlined"
            label={`Rendered size: ${previewFontSize}px`}
          />
        )}
        <Chip
          variant="outlined"
          label={`Area: ${Math.round(region.w * 100)}% × ${Math.round(region.h * 100)}%`}
        />
      </Stack>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        alignItems={{ md: "center" }}
        sx={{ p: 2, borderRadius: 3, border: "1px solid rgba(255,255,255,.08)", bgcolor: "rgba(2,6,23,.25)" }}
      >
        <TextField
          type="number"
          label="Font size"
          value={region.font_size}
          inputProps={{ min: 8, max: 1000 }}
          onChange={(e) =>
            updateRegion({ font_size: Math.max(8, +e.target.value || 8) })
          }
        />
        <TextField
          type="number"
          label="Minimum font size"
          value={region.min_font_size}
          error={region.min_font_size > region.font_size}
          helperText={
            region.min_font_size > region.font_size
              ? "Must not exceed font size"
              : " "
          }
          inputProps={{ min: 8, max: 500 }}
          onChange={(e) =>
            updateRegion({ min_font_size: Math.max(8, +e.target.value || 8) })
          }
        />
        <TextField
          type="number"
          label="Vertical offset (original px)"
          value={region.vertical_offset}
          inputProps={{ min: -1000, max: 1000 }}
          onChange={(e) =>
            updateRegion({
              vertical_offset: Math.max(
                -1000,
                Math.min(1000, +e.target.value || 0),
              ),
            })
          }
        />
        <FormControlLabel
          control={
            <Switch
              checked={region.auto_fit}
              onChange={(e) => updateRegion({ auto_fit: e.target.checked })}
            />
          }
          label="Auto-fit long names"
        />
        <Button
          variant="contained"
          disabled={!regionDirty || region.min_font_size > region.font_size}
          onClick={saveRegion}
        >
          Save placement
        </Button>
      </Stack>
    </Stack>,
    <Stack spacing={3} key="generate">
      <Box>
        <Typography variant="h5">Generate at full resolution</Typography>
        <Typography color="text.secondary">
          Each valid, included, unsent participant gets a unique PDF plus a PNG
          preview. Names use the uploaded font in solid black, shrink to fit
          when enabled, and remain clipped to the placement area.
        </Typography>
      </Box>
      {batch.outdated_certificate_count > 0 && (
        <Alert severity="warning">
          {batch.outdated_certificate_count} certificate
          {batch.outdated_certificate_count === 1 ? " is" : "s are"} outdated
          because participant details or name styling changed. Regenerate before
          previewing, downloading, or sending.
        </Alert>
      )}
      <Stack direction="row" spacing={2}>
        <Button
          variant="contained"
          startIcon={<AutoAwesomeIcon />}
          disabled={
            !batch.template_path ||
            !batch.font_path ||
            !valid.length ||
            batch.generation.status === "RUNNING"
          }
          onClick={() => {
            setError("");
            void api
              .generate(batch.id)
              .then((result) =>
                setNotice(
                  `Generation started for ${result.total} certificates`,
                ),
              )
              .catch((cause) =>
                setError(
                  cause instanceof Error
                    ? cause.message
                    : "Generation could not start",
                ),
              );
          }}
        >
          Generate certificates
        </Button>
        <Button
          component="a"
          href={`/api/batches/${batch.id}/zip`}
          startIcon={<DownloadIcon />}
          disabled={!currentCertificate}
        >
          Download all ZIP
        </Button>
      </Stack>
      <GenerationProgress progress={batch.generation} />
      {currentCertificate ? (
        <Paper sx={{ p: 1.5, bgcolor: "rgba(2,6,23,.35)" }}>
          <img
            style={{
              width: "100%",
              maxHeight: 520,
              objectFit: "contain",
              borderRadius: 10,
            }}
            src={`/api/participants/${currentCertificate.id}/preview`}
            alt="Personalized certificate preview"
          />
        </Paper>
      ) : (
        <Alert severity="info">
          A current personalized preview appears here as generation completes.
        </Alert>
      )}
      <ParticipantTable rows={batch.participants} />
    </Stack>,
    <Stack spacing={3} key="email">
      <Box>
        <Typography variant="h5">Compose the individual email</Typography>
        <Typography color="text.secondary">
          Use {"{name}"} to insert each participant's saved CSV name. HTML is
          intentionally not rendered, preventing injected markup; each message
          receives only its own PDF.
        </Typography>
      </Box>
      {identity ? (
        <Alert severity="success">
          SMTP is configured for {identity}. The From address must be this
          account or an alias listed in the backend environment.
        </Alert>
      ) : (
        <Alert severity="warning">
          SMTP is not configured. Add your Gmail account and Google App Password
          to the root .env file, then restart FastAPI.
        </Alert>
      )}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1.08fr) minmax(340px,.92fr)" },
          gap: 2.5,
          alignItems: "stretch",
        }}
      >
        <Paper className="glass-surface" sx={{ p: { xs: 2, sm: 3 } }}>
          <Stack spacing={2.25}>
            <Box>
              <Typography variant="overline" color="secondary.main">
                Message editor
              </Typography>
              <Typography variant="h6">Personalize every message</Typography>
            </Box>
            <TextField
              label="Sender email"
              type="email"
              value={emailDraft?.sender_email || identity}
              onChange={(e) => changeEmailDraft({ sender_email: e.target.value })}
            />
            <TextField
              label="Subject"
              value={emailDraft?.email_subject ?? batch.email_subject}
              onChange={(e) => changeEmailDraft({ email_subject: e.target.value })}
            />
            <TextField
              label="Plain text body"
              multiline
              minRows={10}
              value={emailDraft?.email_body ?? batch.email_body}
              onChange={(e) => changeEmailDraft({ email_body: e.target.value })}
            />
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
              <Button variant="contained" onClick={emailSave}>
                Save email
              </Button>
              <Button variant="outlined" startIcon={<RefreshIcon />} onClick={restoreDefaultEmailTemplate}>
                Restore Default Template
              </Button>
            </Stack>
          </Stack>
        </Paper>
        <Paper className="glass-surface" sx={{ p: { xs: 2, sm: 3 } }}>
          <Stack spacing={1.75} height="100%">
            <Box>
              <Typography variant="overline" color="secondary.main">
                Live preview
              </Typography>
              <Typography variant="h6">Individual email</Typography>
              <Typography variant="caption" color="text.secondary">
                Previewing the saved participant name: {emailPreviewName}
              </Typography>
            </Box>
            <Divider />
            <Box>
              <Typography variant="caption" color="text.secondary">
                Subject
              </Typography>
              <Typography fontWeight={700}>{emailPreviewSubject}</Typography>
            </Box>
            <Typography className="email-preview-body" variant="body2">
              {emailPreviewBody}
            </Typography>
          </Stack>
        </Paper>
      </Box>
    </Stack>,
    <Stack spacing={3} key="send">
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{ md: "center" }}
      >
        <Box>
          <Typography variant="h5">Send Certificates</Typography>
          <Typography color="text.secondary">
            Monitor the active delivery job. Recipient details remain available
            in the searchable table below.
          </Typography>
        </Box>
        <Button
          size="large"
          variant="contained"
          color="secondary"
          startIcon={<EmailIcon />}
          disabled={!ready || sendBlockedReasons.length > 0 || batch.is_paused}
          onClick={() => {
            setConfirm("");
            setConfirmOpen(true);
          }}
          sx={{ px: 4, py: 1.5 }}
        >
          Send Certificates
        </Button>
      </Stack>
      <StatusCards batch={batch} />
      <AllowanceCards allowance={batch.allowance} />
      {sendBlockedReasons.length > 0 && (
        <Alert severity="info">
          <Typography fontWeight={700}>Sending is not ready:</Typography>
          <ul style={{ marginBottom: 0 }}>
            {sendBlockedReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </Alert>
      )}
      {invalidIncluded > 0 && (
        <Alert severity="info">
          {invalidIncluded} invalid included participant
          {invalidIncluded === 1 ? " is" : "s are"} excluded from sending until
          corrected.
        </Alert>
      )}
      {batch.counts.UNCERTAIN > 0 && (
        <Alert severity="warning">
          Uncertain submissions are excluded from every automatic send and
          retry. Check Gmail Sent and recipient confirmation, then use the
          reconciliation actions in the table. “Not sent” changes the entry to
          Failed; resending still requires the separate Retry Failed
          confirmation.
        </Alert>
      )}
      {batch.outdated_certificate_count > 0 && (
        <Alert severity="warning">
          Regenerate {batch.outdated_certificate_count} outdated certificate
          {batch.outdated_certificate_count === 1 ? " is" : "s are"} before
          sending.
        </Alert>
      )}
      <Alert severity="warning">
        “Sent” means Gmail returned an SMTP acceptance response or an operator
        manually confirmed the message in Gmail Sent. It does not prove inbox
        delivery.
      </Alert>
      <Stack direction="row" useFlexGap flexWrap="wrap" spacing={1}>
        <Button
          variant="outlined"
          startIcon={<PauseIcon />}
          disabled={batch.is_paused}
          onClick={() =>
            run(
              () => api.action(batch.id, "pause"),
              () => setNotice("Sending paused safely"),
            )
          }
        >
          Pause Sending
        </Button>
        <Button
          variant="outlined"
          startIcon={<PlayArrowIcon />}
          disabled={!batch.is_paused || !pending}
          onClick={() =>
            run(
              () => api.action(batch.id, "resume"),
              () => setNotice("Sending resumed"),
            )
          }
        >
          Resume Sending
        </Button>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          disabled={!batch.counts.FAILED}
          onClick={() => setRetryOpen(true)}
        >
          Retry Failed
        </Button>
        <Button
          component="a"
          href={`/api/batches/${batch.id}/report`}
          startIcon={<DownloadIcon />}
        >
          Export Report
        </Button>
      </Stack>
      <Paper className="glass-surface" sx={{ p: { xs: 2, sm: 2.5 } }}>
        <Stack spacing={1}>
          <Stack direction="row" justifyContent="space-between">
            <Typography fontWeight={700}>Live delivery progress</Typography>
            <Typography fontWeight={700}>{Math.round(progress)}%</Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{ height: 10, borderRadius: 5 }}
          />
          {job.current_recipient && (
            <Typography variant="body2">
              Current recipient: <b>{job.current_recipient}</b>
            </Typography>
          )}
          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(125px,1fr))",
              gap: 1,
            }}
          >
            <Typography variant="body2">
              Job total: <b>{job.total || batch.counts.TOTAL}</b>
            </Typography>
            <Typography variant="body2">
              Processed: <b>{job.total ? job.processed : completed}</b>
            </Typography>
            <Typography variant="body2">
              Sent: <b>{job.total ? job.sent : batch.counts.SENT}</b>
            </Typography>
            <Typography variant="body2">
              Failed: <b>{job.total ? job.failed : batch.counts.FAILED}</b>
            </Typography>
            <Typography variant="body2">
              Uncertain:{" "}
              <b>{job.total ? job.uncertain : batch.counts.UNCERTAIN}</b>
            </Typography>
            <Typography variant="body2">
              Pending: <b>{job.total ? job.pending : pending}</b>
            </Typography>
            <Typography variant="body2">
              Sending: <b>{job.total ? job.sending : batch.counts.SENDING}</b>
            </Typography>
            <Typography variant="body2">
              Elapsed: <b>{duration(job.elapsed_seconds)}</b>
            </Typography>
            <Typography variant="body2">
              Estimated remaining:{" "}
              <b>
                {job.processed && job.pending ? duration(job.eta_seconds) : "—"}
              </b>
            </Typography>
          </Box>
        </Stack>
      </Paper>
      {completed > 0 && pending === 0 && batch.counts.SENDING === 0 && (
        <Alert
          severity={
            batch.counts.FAILED || batch.counts.UNCERTAIN
              ? "warning"
              : "success"
          }
        >
          <b>Batch complete.</b> {batch.counts.SENT} accepted,{" "}
          {batch.counts.FAILED} failed, and {batch.counts.UNCERTAIN} uncertain.
        </Alert>
      )}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <TextField
          size="small"
          label="Search name or email"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ flex: 1 }}
        />
        <Select
          size="small"
          value={filter}
          onChange={(e) => setFilter(e.target.value as typeof filter)}
        >
          {["ALL", "PENDING", "SENDING", "SENT", "FAILED", "UNCERTAIN"].map(
            (status) => (
              <MenuItem key={status} value={status}>
                {status}
              </MenuItem>
            ),
          )}
        </Select>
      </Stack>
      <ParticipantTable rows={shown} onReconcile={reconcile} />
    </Stack>,
  ];
  return (
    <>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          background: "rgba(8,11,18,.78)",
          borderBottom: "1px solid rgba(255,255,255,.07)",
          backdropFilter: "blur(18px)",
        }}
      >
        <Container maxWidth="xl">
          <Toolbar disableGutters sx={{ minHeight: { xs: 68, md: 76 } }}>
            <Box sx={{ display: { xs: "none", md: "block" } }}>
              <BrandMark variant="horizontal" width={180} size={60} priority />
            </Box>
            <Box sx={{ display: { xs: "flex", md: "none" }, alignItems: "center" }}>
              <BrandMark size={36} priority />
              <Box sx={{ ml: 1.1 }}>
                <Typography variant="h6" lineHeight={1.05}>CertLoop</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", sm: "block" } }}>
                  Generate. Personalize. Deliver.
                </Typography>
              </Box>
            </Box>
            <Box flex={1} />
            <Box sx={{ display: { xs: "none", sm: "block" }, textAlign: "right", mr: 1.5 }}>
              <Typography variant="caption" color="text.secondary">Current session</Typography>
              <Typography variant="body2" fontWeight={700} noWrap maxWidth={260}>{batch.name}</Typography>
            </Box>
            <Chip size="small" label="Local workspace" color="primary" variant="outlined" />
          </Toolbar>
        </Container>
      </AppBar>
      <Box className="hero-grid" sx={{ pt: { xs: 5, md: 8 }, pb: { xs: 7, md: 10 } }}>
        <Container maxWidth="xl">
          <Typography variant="overline" color="secondary.main">Certificate operations, simplified</Typography>
          <Typography variant="h2" sx={{ mt: 1, maxWidth: 850, fontSize: { xs: "2.45rem", sm: "3.5rem", md: "4.45rem" } }}>
            Generate. Personalize. <Box component="span" sx={{ background: "linear-gradient(135deg,#60A5FA,#38BDF8)", backgroundClip: "text", color: "transparent" }}>Deliver.</Box>
          </Typography>
          <Typography sx={{ color: "text.secondary", mt: 2, maxWidth: 680, fontSize: { xs: "1rem", md: "1.12rem" }, lineHeight: 1.7 }}>
            A focused workflow for creating high-quality certificates and delivering them safely through your authenticated Gmail account.
          </Typography>
        </Container>
      </Box>
      <Container maxWidth="xl" sx={{ mt: { xs: -3, md: -5 }, pb: 5 }}>
        <Paper className="glass-surface" sx={{ p: { xs: 1.5, md: 2.5 }, mb: 2.5 }}>
          <TextField
            select
            fullWidth
            size="small"
            label="Workflow step"
            value={step}
            onChange={(event) => requestStep(Number(event.target.value))}
            sx={{ display: { xs: "block", md: "none" } }}
          >
            {steps.map((label, index) => <MenuItem key={label} value={index}>{index + 1}. {label}</MenuItem>)}
          </TextField>
          <Stepper
            activeStep={step}
            nonLinear
            alternativeLabel
            sx={{ display: { xs: "none", md: "flex" } }}
          >
            {steps.map((label, i) => (
              <Step key={label} completed={i < step}>
                <StepButton onClick={() => requestStep(i)}>{label}</StepButton>
              </Step>
            ))}
          </Stepper>
        </Paper>
        <Paper className="glass-surface" sx={{ p: { xs: 2, sm: 3, lg: 4 } }}>
          {busy && <LinearProgress sx={{ mb: 2 }} />}
          {error && (
            <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Box className="workflow-page" key={step}>{content[step]}</Box>
          <Divider sx={{ my: 3 }} />
          <Stack direction="row" justifyContent="space-between" spacing={2}>
            <Button startIcon={<KeyboardArrowLeftIcon />} disabled={step === 0} onClick={() => requestStep(step - 1)}>
              Back
            </Button>
            <Button
              variant="contained"
              endIcon={<KeyboardArrowRightIcon />}
              disabled={step === steps.length - 1}
              onClick={() => requestStep(step + 1)}
            >
              Continue
            </Button>
          </Stack>
        </Paper>
      </Container>
      <Box component="footer" sx={{ borderTop: "1px solid rgba(255,255,255,.07)", py: 3.5 }}>
        <Container maxWidth="xl">
          <Stack direction={{ xs: "column", sm: "row" }} alignItems={{ xs: "flex-start", sm: "center" }} justifyContent="space-between" spacing={1}>
            <Stack direction="row" spacing={1} alignItems="center">
              <BrandMark size={30} />
              <Typography variant="body2" color="text.secondary">CertLoop — Generate. Personalize. Deliver.</Typography>
            </Stack>
            <Typography variant="caption" color="text.secondary">© {new Date().getFullYear()} CertLoop · Crafted by Kavindu Umayanga</Typography>
          </Stack>
        </Container>
      </Box>
      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <DialogTitle>Confirm bulk delivery</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This will individually submit {ready} messages from{" "}
            {batch.sender_email}. Already sent, uncertain, and outdated entries
            are excluded.
          </Alert>
          <Typography variant="body2" gutterBottom>
            Type <b>SEND {ready}</b> to confirm.
          </Typography>
          <TextField
            autoFocus
            fullWidth
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="secondary"
            disabled={confirm !== `SEND ${ready}`}
            onClick={startSend}
          >
            Start sending
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog open={retryOpen} onClose={() => setRetryOpen(false)}>
        <DialogTitle>Retry definite failures?</DialogTitle>
        <DialogContent>
          <Alert severity="warning">
            This will return {batch.counts.FAILED} definitely failed recipient
            {batch.counts.FAILED === 1 ? "" : "s"} to Pending. SENT and
            UNCERTAIN recipients are never changed.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRetryOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={() =>
              run(
                () => api.action(batch.id, "retry-failed"),
                (result) => {
                  setRetryOpen(false);
                  setNotice(
                    `${(result as { reset: number }).reset} failed recipient(s) returned to Pending`,
                  );
                },
              )
            }
          >
            Retry Failed
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={leaveOpen}
        onClose={() => {
          setLeaveOpen(false);
          setPendingStep(null);
        }}
      >
        <DialogTitle>Unsaved name placement</DialogTitle>
        <DialogContent>
          <Typography>
            Your live preview contains changes that generated certificates will
            not use until you save them.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setLeaveOpen(false);
              setPendingStep(null);
            }}
          >
            Keep editing
          </Button>
          <Button color="warning" onClick={leaveWithoutSaving}>
            Discard changes
          </Button>
          <Button
            variant="contained"
            disabled={region.min_font_size > region.font_size}
            onClick={saveAndLeave}
          >
            Save and continue
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={!!notice}
        autoHideDuration={5000}
        onClose={() => setNotice("")}
        message={notice}
      />
    </>
  );
}
