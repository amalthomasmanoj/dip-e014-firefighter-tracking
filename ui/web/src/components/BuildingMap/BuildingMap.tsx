import { Anchor, EstimatedState } from "../../types/state";
import { MapTransform, worldToMap } from "../../map/transform";
import { AnchorLayer } from "./AnchorLayer";
import { ResponderMarker } from "./ResponderMarker";
import { TrajectoryLayer } from "./TrajectoryLayer";
import { UncertaintyEllipse } from "./UncertaintyEllipse";

type Props = {
  anchors: Anchor[];
  currentState: EstimatedState | null;
  trajectory: EstimatedState[];
};

const transform: MapTransform = {
  scale: 50,
  rotationRad: 0,
  translateX: 72,
  translateY: 390,
};

const axisOrigin = worldToMap({ x: 0, y: 0 }, transform);

export function BuildingMap({ anchors, currentState, trajectory }: Props) {
  const responderPoint = currentState
    ? worldToMap({ x: currentState.position_m.x, y: currentState.position_m.y }, transform)
    : null;

  return (
    <section className="map-panel">
      <svg className="map-svg" viewBox="0 0 720 460" role="img" aria-label="Indoor XY tracking map">
        <defs>
          <pattern id="grid" width="35" height="35" patternUnits="userSpaceOnUse">
            <path d="M 35 0 L 0 0 0 35" fill="none" className="grid-line" />
          </pattern>
        </defs>
        <rect width="720" height="460" fill="url(#grid)" />
        <line className="axis-line" x1={axisOrigin.x} y1={axisOrigin.y} x2="650" y2={axisOrigin.y} />
        <line className="axis-line" x1={axisOrigin.x} y1={axisOrigin.y} x2={axisOrigin.x} y2="58" />
        <AnchorLayer anchors={anchors} transform={transform} />
        <TrajectoryLayer states={trajectory} transform={transform} />
        {currentState && responderPoint ? (
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
      </svg>
    </section>
  );
}
