// API client for the DevAutoPilot backend.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface Incident {
  id: string;
  org_id?: string;
  service: string;
  title: string;
  description?: string | null;
  severity: string;
  type?: string | null;
  status: string;
  confidence?: number | null;
  anomaly_score?: number | null;
  source?: string | null;
  detected_at: string;
}

export interface SimulateResult {
  detected: boolean;
  incident: Incident | null;
}

export async function getHealth(): Promise<{ status: string; service: string }> {
  const res = await fetch(`${API_BASE_URL}/health`);
  return res.json();
}

export async function getIncidents(limit = 50): Promise<Incident[]> {
  const res = await fetch(`${API_BASE_URL}/api/incidents?limit=${limit}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`GET /api/incidents failed: ${res.status}`);
  return res.json();
}

export async function simulateIncident(): Promise<SimulateResult> {
  const res = await fetch(`${API_BASE_URL}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`POST /api/simulate failed: ${res.status}`);
  return res.json();
}
