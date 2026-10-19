import { EstimatedState } from "../types/state";

type Props = {
  state: EstimatedState | null;
};

function speed(state: EstimatedState): number {
  const v = state.velocity_mps;
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

export function headingDegrees(state: EstimatedState): number {
  const q = state.orientation_xyzw;
  const headingRad = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
  const degrees = (headingRad * 180) / Math.PI;
  return (degrees + 360) % 360;
}

export function postureLabel(posture: EstimatedState["activity"]["posture"]): string {
  return posture === "lying_down" ? "lying down" : posture;
}

export function StatePanel({ state }: Props) {
  const prone = state?.activity.posture === "lying_down";

  return (
    <section className="side-panel">
      <h2>State</h2>
      {prone ? (
        <p className="posture-alert" role="status">
          Responder is lying down
        </p>
      ) : null}
      <dl>
        <dt>x</dt>
        <dd>{state ? state.position_m.x.toFixed(2) : "--"} m</dd>
        <dt>y</dt>
        <dd>{state ? state.position_m.y.toFixed(2) : "--"} m</dd>
        <dt>z</dt>
        <dd>{state ? state.position_m.z.toFixed(2) : "--"} m</dd>
        <dt>speed</dt>
        <dd>{state ? speed(state).toFixed(2) : "--"} m/s</dd>
        <dt>heading</dt>
        <dd>{state ? `${headingDegrees(state).toFixed(0)}°` : "--"}</dd>
        <dt>posture</dt>
        <dd className={prone ? "posture-value-alert" : undefined}>
          {state ? postureLabel(state.activity.posture) : "--"}
        </dd>
        <dt>motion</dt>
        <dd>{state ? state.activity.motion : "--"}</dd>
        <dt>activity confidence</dt>
        <dd>{state ? `${Math.round(state.activity.confidence * 100)}%` : "--"}</dd>
      </dl>
    </section>
  );
}
