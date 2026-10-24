import { Box } from "@mui/material";

type BrandMarkProps = {
  variant?: "icon" | "horizontal";
  size?: number;
  width?: number | string;
  priority?: boolean;
};

export default function BrandMark({
  variant = "icon",
  size = 44,
  width,
  priority = false,
}: BrandMarkProps) {
  const horizontal = variant === "horizontal";
  return (
    <Box
      component="img"
      src={
        horizontal
          ? "/branding/certloop-logo.png"
          : "/branding/certloop-icon.png"
      }
      alt={horizontal ? "CertLoop — Generate. Personalize. Deliver." : "CertLoop"}
      loading={priority ? "eager" : "lazy"}
      fetchPriority={priority ? "high" : "auto"}
      draggable={false}
      sx={{
        display: "block",
        width: width ?? (horizontal ? "auto" : size),
        height: horizontal ? (width ? "auto" : size) : size,
        maxWidth: "100%",
        objectFit: "contain",
        objectPosition: "left center",
        flex: "0 0 auto",
        userSelect: "none",
      }}
    />
  );
}
