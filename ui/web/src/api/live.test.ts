import { describe, expect, it } from "vitest";
import { appendLiveTrack, detectedLiveAnchors, pruneStaleLiveTracks } from "./live";
import { Anchor, EstimatedState, LiveAnchorLink, StateMessage } from "../types/state";

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
    let tracks = appendLiveTrack([], message("dwm3000_tag_10", 1), 1_000);
    tracks = appendLiveTrack(tracks, message("dwm3000_tag_11", 5), 1_100);
    tracks = appendLiveTrack(tracks, message("dwm3000_tag_10", 2), 1_200);

    expect(tracks).toHaveLength(2);
    expect(tracks.find((track) => track.node_id === "dwm3000_tag_10")?.trajectory)
      .toHaveLength(2);
    expect(tracks.find((track) => track.node_id === "dwm3000_tag_11")?.trajectory)
      .toHaveLength(1);
    expect(tracks.find((track) => track.node_id === "dwm3000_tag_11")?.state?.position_m.x)
      .toBe(5);
  });

  it("expires old states instead of leaving a frozen avatar on screen", () => {
    const tracks = appendLiveTrack([], message("dwm3000_tag_10", 1), 1_000);

    expect(pruneStaleLiveTracks(tracks, 2_999)).toHaveLength(1);
    expect(pruneStaleLiveTracks(tracks, 3_001)).toEqual([]);
  });
});

describe("live anchor visibility", () => {
  const anchors: Anchor[] = [
    { anchor_id: "A1", x_m: 0, y_m: 0, z_m: 0 },
    { anchor_id: "A2", x_m: 8, y_m: 0, z_m: 0 },
    { anchor_id: "A3", x_m: 0, y_m: 6, z_m: 0 },
  ];

  it("hides configured anchors until a fresh hardware signal names them", () => {
    expect(detectedLiveAnchors(anchors, [], [])).toEqual([]);

    const detected = detectedLiveAnchors(
      anchors,
      [{ anchor_id: "A1", range_m: 2.8, measurement_timestamp_us: 1, age_s: 0.1 }],
      [],
    );

    expect(detected.map((anchor) => anchor.anchor_id)).toEqual(["A1"]);
  });

  it("shows both ends of a fresh valid anchor survey but not stale links", () => {
    const link = (overrides: Partial<LiveAnchorLink>): LiveAnchorLink => ({
      initiator_id: "A1",
      responder_id: "A3",
      timestamp_us: 1,
      sequence_number: 1,
      raw_range_m: 6,
      filtered_range_m: 6,
      valid: true,
      accepted: false,
      age_s: 0.2,
      rssi_gap_db: null,
      rssi_dbm: null,
      ...overrides,
    });

    expect(detectedLiveAnchors(anchors, [], [link({})]).map((anchor) => anchor.anchor_id))
      .toEqual(["A1", "A3"]);
    expect(detectedLiveAnchors(anchors, [], [link({ age_s: 6 })])).toEqual([]);
  });
});
