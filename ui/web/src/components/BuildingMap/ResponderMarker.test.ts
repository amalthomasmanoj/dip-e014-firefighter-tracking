import { describe, expect, it } from "vitest";
import { worldToMap } from "../../map/transform";
import { EstimatedState } from "../../types/state";
import { headingEndpoint } from "./ResponderMarker";

function stateWithYaw(yawRad: number): EstimatedState {
  return {
    timestamp_us: 1,
    position_m: { x: 1, y: 1, z: 0 },
    velocity_mps: { x: 0, y: 0, z: 0 },
    orientation_xyzw: {
      x: 0,
      y: 0,
      z: Math.sin(yawRad / 2),
      w: Math.cos(yawRad / 2),
    },
    uncertainty: {
      sigma_x_m: 0.2,
      sigma_y_m: 0.2,
      sigma_z_m: 1,
    },
    status: {
      zupt_active: false,
      uwb_available: true,
      active_anchor_count: 3,
    },
  };
}

describe("ResponderMarker heading", () => {
  const transform = {
    scale: 50,
    rotationRad: 0,
    translateX: 72,
    translateY: 390,
  };

  it("projects positive world yaw upward in SVG coordinates", () => {
    const state = stateWithYaw(Math.PI / 2);
    const center = worldToMap({ x: state.position_m.x, y: state.position_m.y }, transform);
    const heading = headingEndpoint(state, transform);

    expect(heading.x).toBeCloseTo(center.x);
    expect(heading.y).toBeLessThan(center.y);
  });
});
