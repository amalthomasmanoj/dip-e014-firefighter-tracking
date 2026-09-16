import { EstimatedState } from "../types/state";

const STEP_M = 0.2;
const WALK_SPEED_MPS = 0.8;

export function fallbackDemoState(): EstimatedState {
  return {
    timestamp_us: 1_000_000,
    position_m: { x: 1, y: 1, z: 0 },
    velocity_mps: { x: 0, y: 0, z: 0 },
    orientation_xyzw: headingToQuaternion(0),
    uncertainty: {
      sigma_x_m: 0.2,
      sigma_y_m: 0.24,
      sigma_z_m: 1,
    },
    status: {
      zupt_active: true,
      uwb_available: true,
      active_anchor_count: 3,
    },
    activity: {
      posture: "standing",
      motion: "stationary",
      confidence: 0.95,
    },
  };
}

export function headingToQuaternion(yawRad: number): EstimatedState["orientation_xyzw"] {
  const half = yawRad / 2;
  return {
    x: 0,
    y: 0,
    z: Math.sin(half),
    w: Math.cos(half),
  };
}

export function moveDemoState(state: EstimatedState, dx: number, dy: number): EstimatedState {
  const headingRad = Math.atan2(dy, dx);
  return {
    ...state,
    timestamp_us: state.timestamp_us + 100_000,
    position_m: {
      x: clamp(state.position_m.x + dx * STEP_M, -0.5, 8.5),
      y: clamp(state.position_m.y + dy * STEP_M, -0.5, 6.5),
      z: state.position_m.z,
    },
    velocity_mps: {
      x: dx * WALK_SPEED_MPS,
      y: dy * WALK_SPEED_MPS,
      z: 0,
    },
    orientation_xyzw: headingToQuaternion(headingRad),
    status: {
      ...state.status,
      zupt_active: false,
    },
    activity: {
      ...state.activity,
      motion: "walking",
    },
  };
}

export function stopDemoState(state: EstimatedState): EstimatedState {
  return {
    ...state,
    velocity_mps: { x: 0, y: 0, z: 0 },
    status: {
      ...state.status,
      zupt_active: true,
    },
    activity: {
      ...state.activity,
      motion: "stationary",
    },
  };
}

export function toggleDemoCrouch(state: EstimatedState): EstimatedState {
  return {
    ...state,
    timestamp_us: state.timestamp_us + 1,
    activity: {
      ...state.activity,
      posture: state.activity.posture === "crouching" ? "standing" : "crouching",
      confidence: 0.95,
    },
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
