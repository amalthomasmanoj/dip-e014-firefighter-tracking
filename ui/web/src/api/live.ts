import { FirefighterTrack } from "./simulation";
import {
  Anchor,
  LiveAnchorLink,
  StateMessage,
  UwbRangeReading,
} from "../types/state";

const LIVE_ANCHOR_SIGNAL_MAX_AGE_S = 5;

export function detectedLiveAnchors(
  configuredAnchors: Anchor[],
  ranges: UwbRangeReading[],
  links: LiveAnchorLink[],
): Anchor[] {
  const detectedIds = new Set(ranges.map((range) => range.anchor_id));
  for (const link of links) {
    if (link.valid && link.age_s <= LIVE_ANCHOR_SIGNAL_MAX_AGE_S) {
      detectedIds.add(link.initiator_id);
      detectedIds.add(link.responder_id);
    }
  }
  return configuredAnchors.filter((anchor) => detectedIds.has(anchor.anchor_id));
}

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
