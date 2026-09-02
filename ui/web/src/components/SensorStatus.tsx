import { EstimatedState } from "../types/state";

type Props = {
  state: EstimatedState | null;
  connected: boolean;
};

export function SensorStatus({ state, connected }: Props) {
  return (
    <section className="side-panel">
      <h2>Sensors</h2>
      <dl>
        <dt>IMU</dt>
        <dd>simulation</dd>
        <dt>UWB</dt>
        <dd>{state?.status.uwb_available ? "available" : "unknown"}</dd>
        <dt>anchors</dt>
        <dd>{state ? state.status.active_anchor_count : "--"}</dd>
        <dt>ZUPT</dt>
        <dd>{state?.status.zupt_active ? "active" : "inactive"}</dd>
        <dt>connection</dt>
        <dd>{connected ? "simulation live" : "offline"}</dd>
      </dl>
    </section>
  );
}

