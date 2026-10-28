import { BackendHealth, BackendSource, LiveUwbSnapshot } from "../types/state";

const baseUrl = import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://localhost:8000";

export async function fetchBackendHealth(): Promise<BackendHealth> {
  const response = await fetch(`${baseUrl}/health`);
  if (!response.ok) {
    throw new Error(`failed to load backend health: ${response.status}`);
  }
  return response.json() as Promise<BackendHealth>;
}

export function backendSourceFromHealth(health: BackendHealth): BackendSource {
  return health.source === "udp" ? "live" : health.source;
}

export async function fetchLiveUwbRanges(): Promise<LiveUwbSnapshot> {
  const response = await fetch(`${baseUrl}/uwb/ranges`);
  if (!response.ok) {
    throw new Error(`failed to load live UWB ranges: ${response.status}`);
  }
  return response.json() as Promise<LiveUwbSnapshot>;
}

export async function alignResponderHeading(
  responderId: string,
  headingRad = 0,
): Promise<void> {
  const response = await fetch(
    `${baseUrl}/responders/${encodeURIComponent(responderId)}/heading-alignment`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ heading_rad: headingRad }),
    },
  );
  if (!response.ok) {
    throw new Error(`failed to align heading: ${response.status}`);
  }
}
