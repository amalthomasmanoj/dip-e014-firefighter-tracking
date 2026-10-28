import { useState } from "react";
import { EstimatedState } from "../types/state";

type Props = {
  state: EstimatedState | null;
  onAlignHeading?: () => Promise<void>;
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

export function StatePanel({ state, onAlignHeading }: Props) {
  const prone = state?.activity.posture === "lying_down";
  const [alignmentStatus, setAlignmentStatus] = useState<string | null>(null);

  async function alignHeading() {
    if (!onAlignHeading) return;
    setAlignmentStatus("Aligning…");
    try {
      await onAlignHeading();
      setAlignmentStatus("Facing aligned to building +X");
    } catch {
      setAlignmentStatus("Heading alignment failed");
    }
  }

  return (
    <section className="side-panel">
      <h2>State</h2>
      {prone ? (
        <p className="posture-alert" role="status">
          Lying down — check responder
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
      {onAlignHeading ? (
        <div className="heading-alignment">
          <button type="button" onClick={() => void alignHeading()}>
            Align facing to building +X
          </button>
          {alignmentStatus ? <p role="status">{alignmentStatus}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
