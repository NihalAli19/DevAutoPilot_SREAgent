// StatusBadge — colored badge for severity values (P1..P4).
const SEVERITY_STYLES: Record<string, string> = {
  P1: "bg-red-500/20 text-red-300 border-red-500/40",
  P2: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  P3: "bg-yellow-500/20 text-yellow-300 border-yellow-500/40",
  P4: "bg-sky-500/20 text-sky-300 border-sky-500/40",
};

export default function StatusBadge({ label }: { label?: string }) {
  const key = (label ?? "").toUpperCase();
  const style = SEVERITY_STYLES[key] ?? "bg-slate-500/20 text-slate-300 border-slate-500/40";
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold ${style}`}>
      {label ?? "—"}
    </span>
  );
}
