import { Anchor, EstimatedState, UwbRangeReading } from "../types/state";

export type SimulatedFirefighter = {
  node_id: string;
  label: string;
  state: EstimatedState | null;
  ranges: UwbRangeReading[];
};
export type FirefighterTrack = SimulatedFirefighter & { trajectory: EstimatedState[] };
export type AnchorLink = {
  initiator_id: string;
  responder_id: string;
  timestamp_us: number;
  sequence_number: number;
  raw_range_m: number;
  valid: boolean;
};
export type SimulationSnapshot = {
  source: "simulation";
  timestamp_us: number;
  map_version: number;
  frame: "fixed_world";
  geometry_valid: boolean;
  anchors: Anchor[];
  firefighters: SimulatedFirefighter[];
  anchor_links: AnchorLink[];
};
export type SimulationCommand = {
  kind: "firefighter" | "anchor";
  node_id: string;
  action?: "move" | "toggle_crouch";
  dx_m?: number;
  dy_m?: number;
};
const baseUrl = import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://localhost:8000";

export async function fetchSimulation(): Promise<SimulationSnapshot> {
  const response = await fetch(`${baseUrl}/simulation`, { signal: AbortSignal.timeout(1500) });
  if (!response.ok) throw new Error(`Simulation unavailable (${response.status})`);
  return response.json() as Promise<SimulationSnapshot>;
}

export async function sendSimulationCommand(command: SimulationCommand): Promise<void> {
  const response = await fetch(`${baseUrl}/simulation/command`, {
    method: "POST",
    signal: AbortSignal.timeout(1500),
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(command),
  });
  if (!response.ok) throw new Error(`Movement rejected (${response.status})`);
}

export function appendSimulationTracks(
  previous: FirefighterTrack[], snapshot: SimulationSnapshot,
): FirefighterTrack[] {
  return snapshot.firefighters.map((firefighter) => {
    let history = previous.find((item) => item.node_id === firefighter.node_id)?.trajectory ?? [];
    const state = firefighter.state;
    // A restarted backend starts a fresh simulation clock and trajectory.
    if (state && state.timestamp_us < (history.at(-1)?.timestamp_us ?? -1)) history = [];
    return {
      ...firefighter,
      trajectory: state && state.timestamp_us > (history.at(-1)?.timestamp_us ?? -1)
        ? [...history.slice(-179), state] : history,
    };
  });
}
