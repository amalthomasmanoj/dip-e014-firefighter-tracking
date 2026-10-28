import {
  BackendHealth,
  BackendSource,
  LiveAnchorMapSnapshot,
  LiveUwbSnapshot,
} from "../types/state";

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

export async function fetchLiveUwbRanges(tagNodeId?: string): Promise<LiveUwbSnapshot> {
  const query = tagNodeId ? `?tag_node_id=${encodeURIComponent(tagNodeId)}` : "";
  const response = await fetch(`${baseUrl}/uwb/ranges${query}`);
  if (!response.ok) {
    throw new Error(`failed to load live UWB ranges: ${response.status}`);
  }
  return response.json() as Promise<LiveUwbSnapshot>;
}

export async function fetchLiveAnchorMap(): Promise<LiveAnchorMapSnapshot> {
  const response = await fetch(`${baseUrl}/uwb/anchor-map`);
  if (!response.ok) {
    throw new Error(`failed to load live anchor map: ${response.status}`);
  }
  return response.json() as Promise<LiveAnchorMapSnapshot>;
}
