import { EstimatedState } from "../types/state";

type Props = {
  state: EstimatedState | null;
};

function speed(state: EstimatedState): number {
  const v = state.velocity_mps;
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

export function StatePanel({ state }: Props) {
  return (
    <section className="side-panel">
      <h2>State</h2>
      <dl>
        <dt>x</dt>
        <dd>{state ? state.position_m.x.toFixed(2) : "--"} m</dd>
        <dt>y</dt>
        <dd>{state ? state.position_m.y.toFixed(2) : "--"} m</dd>
        <dt>z</dt>
        <dd>{state ? state.position_m.z.toFixed(2) : "--"} m</dd>
        <dt>speed</dt>
        <dd>{state ? speed(state).toFixed(2) : "--"} m/s</dd>
      </dl>
    </section>
  );
}

