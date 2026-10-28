import { describe, expect, it } from "vitest";
import { headingDegrees, postureLabel } from "./StatePanel";
import { EstimatedState } from "../types/state";

function stateWithHeading(headingRad: number): EstimatedState {
  const half = headingRad / 2;
  return {
    timestamp_us: 1,
    position_m: { x: 0, y: 0, z: 0 },
    velocity_mps: { x: 0, y: 0, z: 0 },
    orientation_xyzw: { x: 0, y: 0, z: Math.sin(half), w: Math.cos(half) },
    uncertainty: { sigma_x_m: 0.1, sigma_y_m: 0.1, sigma_z_m: 1 },
    status: { zupt_active: false, uwb_available: true, active_anchor_count: 3 },
    activity: { posture: "standing", motion: "stationary", confidence: 0.8 },
  };
}

describe("headingDegrees", () => {
  it("reports 0 degrees along +x", () => {
    expect(headingDegrees(stateWithHeading(0))).toBeCloseTo(0, 6);
  });

  it("reports 90 degrees along +y", () => {
    expect(headingDegrees(stateWithHeading(Math.PI / 2))).toBeCloseTo(90, 6);
  });

  it("maps negative headings into 0..360", () => {
    expect(headingDegrees(stateWithHeading(-Math.PI / 2))).toBeCloseTo(270, 6);
  });
});

describe("postureLabel", () => {
  it("humanizes the lying_down contract value", () => {
    expect(postureLabel("lying_down")).toBe("lying down");
  });

  it("passes other postures through unchanged", () => {
    expect(postureLabel("standing")).toBe("standing");
    expect(postureLabel("crouching")).toBe("crouching");
  });
});
