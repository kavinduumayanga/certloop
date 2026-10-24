import { alpha, createTheme } from "@mui/material/styles";

export const colors = {
  background: "#080B12",
  surface: "#0D111C",
  card: "#111827",
  cardStrong: "#151E2F",
  primary: "#2563EB",
  electric: "#38BDF8",
  text: "#F8FAFC",
  muted: "#94A3B8",
  success: "#22C55E",
  warning: "#F59E0B",
  error: "#F87171",
};

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: colors.primary, light: colors.electric },
    secondary: { main: colors.electric },
    success: { main: colors.success },
    warning: { main: colors.warning },
    error: { main: colors.error },
    background: { default: colors.background, paper: colors.card },
    text: { primary: colors.text, secondary: colors.muted },
    divider: alpha("#FFFFFF", 0.09),
  },
  typography: {
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    h2: { fontWeight: 780, letterSpacing: "-0.045em", lineHeight: 1.04 },
    h3: { fontWeight: 760, letterSpacing: "-0.04em", lineHeight: 1.08 },
    h4: { fontWeight: 740, letterSpacing: "-0.035em" },
    h5: { fontWeight: 720, letterSpacing: "-0.025em" },
    h6: { fontWeight: 700, letterSpacing: "-0.015em" },
    button: { fontWeight: 700, letterSpacing: "-0.01em" },
    overline: { fontWeight: 750, letterSpacing: "0.12em" },
  },
  shape: { borderRadius: 16 },
  components: {
    MuiCssBaseline: { styleOverrides: { body: { backgroundColor: colors.background, color: colors.text } } },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { backgroundImage: "none", border: `1px solid ${alpha("#FFFFFF", 0.08)}`, boxShadow: "0 18px 60px rgba(0,0,0,.2)" } },
    },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          background: `linear-gradient(145deg, ${alpha(colors.cardStrong, 0.94)}, ${alpha(colors.surface, 0.9)})`,
          border: `1px solid ${alpha("#FFFFFF", 0.08)}`,
          transition: "transform .2s ease, border-color .2s ease, box-shadow .2s ease",
          "&:hover": { transform: "translateY(-2px)", borderColor: alpha(colors.electric, 0.25), boxShadow: "0 18px 50px rgba(0,0,0,.28)" },
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          minHeight: 42,
          paddingInline: 18,
          textTransform: "none",
          borderRadius: 11,
          transition: "transform .18s ease, box-shadow .18s ease, background-color .18s ease",
          "&:focus-visible": { outline: `3px solid ${alpha(colors.electric, 0.38)}`, outlineOffset: 2 },
        },
        containedPrimary: {
          background: `linear-gradient(135deg, ${colors.primary}, ${colors.electric})`,
          color: "#FFFFFF",
          boxShadow: `0 10px 28px ${alpha(colors.primary, 0.28)}`,
          "&:hover": { transform: "translateY(-1px)", boxShadow: `0 14px 34px ${alpha(colors.primary, 0.38)}` },
        },
        outlined: {
          borderColor: alpha("#FFFFFF", 0.14),
          background: alpha("#FFFFFF", 0.025),
          "&:hover": { borderColor: alpha(colors.electric, 0.5), background: alpha(colors.electric, 0.07) },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          backgroundColor: alpha("#020617", 0.32),
          transition: "background-color .2s ease, box-shadow .2s ease",
          "& .MuiOutlinedInput-notchedOutline": { borderColor: alpha("#FFFFFF", 0.12) },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: alpha(colors.electric, 0.42) },
          "&.Mui-focused": { backgroundColor: alpha("#020617", 0.5), boxShadow: `0 0 0 3px ${alpha(colors.primary, 0.15)}` },
        },
      },
    },
    MuiInputLabel: { styleOverrides: { root: { color: colors.muted } } },
    MuiChip: { styleOverrides: { root: { borderRadius: 9, fontWeight: 650 }, outlined: { backgroundColor: alpha("#FFFFFF", 0.025) } } },
    MuiAlert: { styleOverrides: { root: { borderRadius: 13, border: `1px solid ${alpha("#FFFFFF", 0.08)}`, alignItems: "center" } } },
    MuiLinearProgress: {
      styleOverrides: {
        root: { backgroundColor: alpha(colors.primary, 0.15), borderRadius: 999 },
        bar: { borderRadius: 999, background: `linear-gradient(90deg, ${colors.primary}, ${colors.electric})`, transition: "transform .45s ease" },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottomColor: alpha("#FFFFFF", 0.07) },
        head: { color: "#CBD5E1", fontSize: ".72rem", fontWeight: 750, letterSpacing: ".06em", textTransform: "uppercase", backgroundColor: alpha(colors.surface, 0.96), backdropFilter: "blur(14px)" },
      },
    },
    MuiTableRow: { styleOverrides: { root: { "&:hover": { backgroundColor: `${alpha(colors.electric, 0.035)} !important` } } } },
    MuiDialog: { styleOverrides: { paper: { background: `linear-gradient(145deg, ${colors.cardStrong}, ${colors.surface})`, border: `1px solid ${alpha(colors.electric, 0.16)}`, boxShadow: "0 30px 100px rgba(0,0,0,.62)" } } },
    MuiDialogTitle: { styleOverrides: { root: { fontWeight: 740 } } },
    MuiTooltip: { styleOverrides: { tooltip: { backgroundColor: "#172033", fontSize: ".78rem" } } },
    MuiSnackbarContent: { styleOverrides: { root: { background: colors.cardStrong, border: `1px solid ${alpha(colors.electric, 0.22)}`, borderRadius: 12 } } },
  },
});
