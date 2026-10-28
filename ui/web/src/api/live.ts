import { FirefighterTrack } from "./simulation";
import { StateMessage } from "../types/state";

export function appendLiveTrack(
  previous: FirefighterTrack[],
  message: StateMessage,
): FirefighterTrack[] {
  const nodeId = message.node_id ?? "live_tag";
  const existing = previous.find((track) => track.node_id === nodeId);
  const updated: FirefighterTrack = {
    node_id: nodeId,
    label: nodeId.replace("dwm3000_tag_", "Firefighter "),
    state: message.state,
    ranges: existing?.ranges ?? [],
    trajectory: [...(existing?.trajectory ?? []).slice(-179), message.state],
  };
  return existing
    ? previous.map((track) => track.node_id === nodeId ? updated : track)
    : [...previous, updated];
}
