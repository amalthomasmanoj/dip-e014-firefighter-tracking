const baseUrl = import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://localhost:8000";

export type HeartRateSnapshot = {
  monitor?: HeartRateMonitor;
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

export type AlertSettings = {
  enabled: boolean;
  low_bpm: number;
  high_bpm: number;
  low_duration_s: number;
  high_duration_s: number;
  hysteresis_bpm: number;
  signal_loss_s: number;
};
export type HeartRatePoint = { timestamp_us: number; bpm: number };
export type HeartRateAlert = {
  id: number;
  kind: "high" | "low" | "signal_loss";
  bpm: number | null;
  started_us: number;
  duration_s: number;
  acknowledged: boolean;
  ended_us: number | null;
  end_reason: string | null;
};
export type HeartRateMonitor = {
  settings: AlertSettings;
  pending: { kind: "high" | "low"; elapsed_s: number } | null;
  active: HeartRateAlert | null;
  events: HeartRateAlert[];
  history: HeartRatePoint[];
};
export async function saveAlertSettings(settings: AlertSettings): Promise<void> {
  const response = await fetch(`${baseUrl}/heart-rate/settings`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!response.ok) throw new Error("Settings rejected. Check limits and hysteresis.");
}
export async function acknowledgeAlert(id: number): Promise<void> {
  const response = await fetch(`${baseUrl}/heart-rate/alerts/${id}/acknowledge`, { method: "POST" });
  if (!response.ok) throw new Error("Could not acknowledge alert.");
}
