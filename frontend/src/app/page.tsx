// Dashboard — live incident feed + stats + a Simulate trigger.
"use client";

import { useCallback, useEffect, useState } from "react";

import LiveFeed from "@/components/LiveFeed";
import { getIncidents, simulateIncident, type Incident } from "@/lib/api";

export default function DashboardPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setIncidents(await getIncidents());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load incidents");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000); // live feed: poll every 5s
    return () => clearInterval(id);
  }, [refresh]);

  const onSimulate = useCallback(async () => {
    setBusy(true);
    try {
      await simulateIncident();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "simulate failed");
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const open = incidents.filter((i) => i.status === "open").length;

  return (
    <main className="mx-auto max-w-3xl p-6 text-slate-100">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">DevAutoPilot — Dashboard</h1>
        <button
          onClick={onSimulate}
          disabled={busy}
          className="rounded bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {busy ? "Simulating…" : "Simulate incident"}
        </button>
      </div>

      <div className="mt-4 flex gap-6 text-sm text-slate-400">
        <span>Total: {incidents.length}</span>
        <span>Open: {open}</span>
      </div>

      {error ? (
        <p className="mt-4 text-sm text-red-400">
          {error} — is the backend running on the configured API URL?
        </p>
      ) : null}

      <section className="mt-6">
        <LiveFeed incidents={incidents} />
      </section>
    </main>
  );
}
