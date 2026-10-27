const baseUrl = import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://localhost:8000";

export type HeartRateSnapshot = {
  source: "ble";
  wearer: string;
  device_name: string | null;
  status: "disabled" | "scanning" | "connecting" | "connected" | "waiting" |
    "stale" | "no_contact" | "disconnected" | "error";
  bpm: number | null;
  timestamp_us: number | null;
  age_s: number | null;
  error: string | null;
};

export async function fetchHeartRate(signal?: AbortSignal): Promise<HeartRateSnapshot> {
  const response = await fetch(`${baseUrl}/heart-rate`, { signal });
  if (!response.ok) throw new Error(`failed to load heart rate: ${response.status}`);
  return response.json() as Promise<HeartRateSnapshot>;
}
