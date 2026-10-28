import { describe, expect, it } from "vitest";
import { appendLiveTrack } from "./live";
import { EstimatedState, StateMessage } from "../types/state";

function state(x: number): EstimatedState {
  return {
    timestamp_us: x * 1_000,
    position_m: { x, y: 1, z: 0 },
    velocity_mps: { x: 0, y: 0, z: 0 },
    orientation_xyzw: { x: 0, y: 0, z: 0, w: 1 },
    uncertainty: { sigma_x_m: 0.2, sigma_y_m: 0.2, sigma_z_m: 1 },
    status: { zupt_active: false, uwb_available: true, active_anchor_count: 3 },
    activity: { posture: "standing", motion: "stationary", confidence: 1 },
  };
}

function message(nodeId: string, x: number): StateMessage {
  return {
    type: "estimated_state",
    source: "live",
    node_id: nodeId,
    state: state(x),
  };
}

describe("live tag tracks", () => {
  it("keeps each tag's state and trajectory independent", () => {
    let tracks = appendLiveTrack([], message("dwm3000_tag_10", 1));
    tracks = appendLiveTrack(tracks, message("dwm3000_tag_11", 5));
    tracks = appendLiveTrack(tracks, message("dwm3000_tag_10", 2));

    expect(tracks).toHaveLength(2);
    expect(tracks.find((track) => track.node_id === "dwm3000_tag_10")?.trajectory)
      .toHaveLength(2);
    expect(tracks.find((track) => track.node_id === "dwm3000_tag_11")?.trajectory)
      .toHaveLength(1);
    expect(tracks.find((track) => track.node_id === "dwm3000_tag_11")?.state?.position_m.x)
      .toBe(5);
  });
});
