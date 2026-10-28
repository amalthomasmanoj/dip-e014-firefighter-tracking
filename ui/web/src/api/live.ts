import { FirefighterTrack } from "./simulation";
import {
  Anchor,
  LiveAnchorLink,
  StateMessage,
  UwbRangeReading,
} from "../types/state";

const LIVE_ANCHOR_SIGNAL_MAX_AGE_S = 5;
export const LIVE_STATE_MAX_AGE_MS = 2_000;

export type LiveFirefighterTrack = FirefighterTrack & {
  received_at_ms: number;
};

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
  previous: LiveFirefighterTrack[],
  message: StateMessage,
  receivedAtMs = Date.now(),
): LiveFirefighterTrack[] {
  const nodeId = message.node_id ?? "live_tag";
  const existing = previous.find((track) => track.node_id === nodeId);
  const updated: LiveFirefighterTrack = {
    node_id: nodeId,
    label: nodeId.replace("dwm3000_tag_", "Firefighter "),
    state: message.state,
    ranges: existing?.ranges ?? [],
    trajectory: [...(existing?.trajectory ?? []).slice(-179), message.state],
    received_at_ms: receivedAtMs,
  };
  return existing
    ? previous.map((track) => track.node_id === nodeId ? updated : track)
    : [...previous, updated];
}

export function pruneStaleLiveTracks(
  tracks: LiveFirefighterTrack[],
  nowMs = Date.now(),
  maxAgeMs = LIVE_STATE_MAX_AGE_MS,
): LiveFirefighterTrack[] {
  const fresh = tracks.filter((track) => nowMs - track.received_at_ms <= maxAgeMs);
  return fresh.length === tracks.length ? tracks : fresh;
}
