import { backendHttpUrl } from "./server";

export type HeartRateSnapshot = {
  source: "ble";
  responder_id: string | null;
  wearer: string;
  device_name: string | null;
  status: "disabled" | "scanning" | "connecting" | "connected" | "waiting" |
    "stale" | "no_contact" | "disconnected" | "error";
  bpm: number | null;
  received_timestamp_us: number | null;
  age_s: number | null;
  error: string | null;
};

export function heartRateMatchesResponder(
  snapshot: HeartRateSnapshot | null,
  selectedResponderId?: string,
): boolean {
  return !selectedResponderId || snapshot?.responder_id === selectedResponderId;
}

export async function fetchHeartRate(signal?: AbortSignal): Promise<HeartRateSnapshot> {
  const baseUrl = backendHttpUrl();
  const response = await fetch(`${baseUrl}/heart-rate`, { signal });
  if (!response.ok) throw new Error(`failed to load heart rate: ${response.status}`);
  return response.json() as Promise<HeartRateSnapshot>;
}
