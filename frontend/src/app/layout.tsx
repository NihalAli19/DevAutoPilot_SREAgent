// Root layout for the dark SRE control center.
// TODO(plan: Phase 4/5) — add Sidebar, theme, and fonts.
import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "DevAutoPilot v2",
  description: "AI SRE platform — ML anomaly detection + multi-agent LLM workflow.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
