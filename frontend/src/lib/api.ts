// API client for the DevAutoPilot backend.
// TODO(plan: Phase 2) — typed fetch wrappers for each endpoint.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<{ status: string; service: string }> {
  const res = await fetch(`${API_BASE_URL}/health`);
  return res.json();
}
