// IncidentCard — summary card for a single incident.
import type { Incident } from "@/lib/api";
import StatusBadge from "./StatusBadge";

export default function IncidentCard({ incident }: { incident: Incident }) {
  const score =
    incident.anomaly_score != null ? incident.anomaly_score.toFixed(3) : "—";
  const confidence =
    incident.confidence != null ? `${Math.round(incident.confidence * 100)}%` : "—";
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium text-slate-100">{incident.title}</span>
        <StatusBadge label={incident.severity} />
      </div>
      <div className="mt-1 text-sm text-slate-400">
        {incident.service}
        {incident.type ? ` · ${incident.type}` : ""} · {incident.status}
      </div>
      <div className="mt-2 flex gap-4 text-xs text-slate-500">
        <span>anomaly {score}</span>
        <span>confidence {confidence}</span>
        <span>{new Date(incident.detected_at).toLocaleString()}</span>
      </div>
    </div>
  );
}
