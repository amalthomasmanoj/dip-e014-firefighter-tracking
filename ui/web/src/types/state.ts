export type Vector3 = {
  x: number;
  y: number;
  z: number;
};

export type Quaternion = {
  x: number;
  y: number;
  z: number;
  w: number;
};

export type EstimatedState = {
  timestamp_us: number;
  position_m: Vector3;
  velocity_mps: Vector3;
  orientation_xyzw: Quaternion;
  uncertainty: {
    sigma_x_m: number;
    sigma_y_m: number;
    sigma_z_m: number;
  };
  status: {
    zupt_active: boolean;
    uwb_available: boolean;
    active_anchor_count: number;
  };
};

export type StateMessage = {
  type: "estimated_state";
  source: "simulation" | "live" | "replay";
  state: EstimatedState;
};

export type Anchor = {
  anchor_id: string;
  x_m: number;
  y_m: number;
  z_m: number;
};

