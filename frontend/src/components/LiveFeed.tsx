// LiveFeed — feed of recent incidents.
import type { Incident } from "@/lib/api";
import IncidentCard from "./IncidentCard";

export default function LiveFeed({ incidents }: { incidents: Incident[] }) {
  if (incidents.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No incidents yet. Trigger one with “Simulate incident”.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {incidents.map((incident) => (
        <IncidentCard key={incident.id} incident={incident} />
      ))}
    </div>
  );
}
