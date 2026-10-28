import { describe, expect, it } from "vitest";
import { heartRateMatchesResponder, HeartRateSnapshot } from "./heartRate";

const snapshot: HeartRateSnapshot = {
  source: "ble",
  responder_id: "firefighter_1",
  wearer: "Responder 1",
  device_name: "H808S",
  status: "connected",
  bpm: 72,
  received_timestamp_us: 1,
  age_s: 0.1,
  error: null,
};

describe("heart-rate responder association", () => {
  it("matches only the assigned selected responder", () => {
    expect(heartRateMatchesResponder(snapshot, "firefighter_1")).toBe(true);
    expect(heartRateMatchesResponder(snapshot, "firefighter_2")).toBe(false);
  });

  it("allows an unfiltered operations view", () => {
    expect(heartRateMatchesResponder(snapshot)).toBe(true);
  });
});
