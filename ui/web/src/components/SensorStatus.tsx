import { BackendSource, EstimatedState, LiveUwbSnapshot } from "../types/state";

type Props = {
  state: EstimatedState | null;
  connected: boolean;
  source: BackendSource | null;
  liveUwb: LiveUwbSnapshot | null;
};

export function SensorStatus({ state, connected, source, liveUwb }: Props) {
  const liveAnchorCount = liveUwb?.active_anchor_count ?? 0;
  const uwbStatus = source === "live"
    ? liveUwb?.tag_present
      ? "live"
      : "waiting"
    : state?.status.uwb_available
      ? "available"
      : "simulation";

  return (
    <section className="side-panel">
      <h2>Sensors</h2>
      <dl>
        <dt>IMU</dt>
        <dd>{source === "live" ? "waiting/live input" : "simulation"}</dd>
        <dt>UWB</dt>
        <dd>{uwbStatus}</dd>
        <dt>tag</dt>
        <dd>{liveUwb?.tag_present ? liveUwb.tag_node_id : source === "live" ? "not detected" : "demo"}</dd>
        <dt>anchors</dt>
        <dd>{source === "live" ? liveAnchorCount : state?.status.active_anchor_count ?? "--"}</dd>
        <dt>ZUPT</dt>
        <dd>{state?.status.zupt_active ? "active" : "inactive"}</dd>
        <dt>connection</dt>
        <dd>{connected ? `${source ?? "unknown"} connected` : "offline"}</dd>
      </dl>
      {liveUwb?.ranges.length ? (
        <ul className="range-list">
          {liveUwb.ranges.map((range) => (
            <li key={range.anchor_id}>
              <span>{range.anchor_id}</span>
              <strong>{range.range_m.toFixed(2)} m</strong>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
