import { AnchorLink, FirefighterTrack } from "../../api/simulation";
import { Anchor, EstimatedState, LiveUwbSnapshot } from "../../types/state";
import { MapTransform, worldToMap } from "../../map/transform";
import { AnchorLayer } from "./AnchorLayer";
import { ResponderMarker } from "./ResponderMarker";
import { TrajectoryLayer } from "./TrajectoryLayer";
import { UncertaintyEllipse } from "./UncertaintyEllipse";
import { UwbRangeLayer } from "./UwbRangeLayer";

type Props = {
  anchors: Anchor[];
  currentState: EstimatedState | null;
  trajectory: EstimatedState[];
  liveUwb: LiveUwbSnapshot | null;
  usableAnchorCount: number;
  firefighters?: FirefighterTrack[];
  anchorLinks?: AnchorLink[];
};

const transform: MapTransform = {
  scale: 50,
  rotationRad: 0,
  translateX: 72,
  translateY: 390,
};

const axisOrigin = worldToMap({ x: 0, y: 0 }, transform);

export function BuildingMap({
  anchors,
  currentState,
  trajectory,
  liveUwb,
  usableAnchorCount,
  firefighters,
  anchorLinks = [],
}: Props) {
  const responderPoint = currentState
    ? worldToMap({ x: currentState.position_m.x, y: currentState.position_m.y }, transform)
    : null;

  return (
    <section className="map-panel">
      <svg className="map-svg" viewBox="0 0 720 460" role="img" aria-label="Indoor XY tracking map" tabIndex={0}>
        <defs>
          <pattern id="grid" width="35" height="35" patternUnits="userSpaceOnUse">
            <path d="M 35 0 L 0 0 0 35" fill="none" className="grid-line" />
          </pattern>
        </defs>
        <rect width="720" height="460" fill="url(#grid)" />
        <line className="axis-line" x1={axisOrigin.x} y1={axisOrigin.y} x2="650" y2={axisOrigin.y} />
        <line className="axis-line" x1={axisOrigin.x} y1={axisOrigin.y} x2={axisOrigin.x} y2="58" />
        <UwbRangeLayer
          anchors={anchors}
          state={currentState}
          ranges={liveUwb?.ranges ?? []}
          transform={transform}
        />
        {anchorLinks.map((link) => {
          const start = anchors.find((a) => a.anchor_id === link.initiator_id);
          const end = anchors.find((a) => a.anchor_id === link.responder_id);
          if (!start || !end) return null;
          const a = worldToMap({ x: start.x_m, y: start.y_m }, transform);
          const b = worldToMap({ x: end.x_m, y: end.y_m }, transform);
          return <g key={`${link.initiator_id}-${link.responder_id}`} aria-label={`Simulated link ${link.initiator_id} to ${link.responder_id}`}>
            <line className="anchor-peer-link" x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
            <text className="uwb-range-label" x={(a.x + b.x) / 2 + 8} y={(a.y + b.y) / 2 - 8}>{link.raw_range_m.toFixed(2)} m</text>
          </g>;
        })}
        <AnchorLayer anchors={anchors} transform={transform} />
        {firefighters?.map((tag, index) => {
          const state = tag.state;
          const point = state ? worldToMap({ x: state.position_m.x, y: state.position_m.y }, transform) : null;
          return <g key={tag.node_id} className={`firefighter-track firefighter-${index}`}>
            <TrajectoryLayer states={tag.trajectory} transform={transform} />
            {state && point ? <>
              <UncertaintyEllipse state={state} cx={point.x} cy={point.y} transform={transform} />
              <ResponderMarker state={state} cx={point.x} cy={point.y} transform={transform} />
              <text className="firefighter-label" x={point.x + 14} y={point.y - 16}>{tag.label}</text>
            </> : null}
          </g>;
        })}
        {!firefighters ? <TrajectoryLayer states={trajectory} transform={transform} /> : null}
        {!firefighters && currentState && responderPoint ? (
          <>
            <UncertaintyEllipse
              state={currentState}
              cx={responderPoint.x}
              cy={responderPoint.y}
              transform={transform}
            />
            <ResponderMarker
              state={currentState}
              cx={responderPoint.x}
              cy={responderPoint.y}
              transform={transform}
            />
          </>
        ) : null}
        {liveUwb?.tag_present && !currentState ? (
          <g className="unresolved-tag" transform="translate(470 28)">
            <circle cx="10" cy="8" r="6" />
            <path d="M10 15 L10 31 M1 21 L19 21 M10 31 L3 42 M10 31 L17 42" />
            <text x="28" y="18">TAG DETECTED</text>
            <text x="28" y="36">
              position unresolved · {usableAnchorCount}/3 mapped anchors
            </text>
          </g>
        ) : null}
      </svg>
    </section>
  );
}
