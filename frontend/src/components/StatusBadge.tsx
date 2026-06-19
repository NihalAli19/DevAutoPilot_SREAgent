// StatusBadge — colored badge for severity/status values.
// TODO(plan: Phase 2) — map severity/status to theme colors.
export default function StatusBadge({ label }: { label?: string }) {
  return <span>{label ?? ""}</span>;
}
