import { EstimatedState } from "../../types/state";
import { MapTransform, WorldPoint, worldToMap } from "../../map/transform";

type Props = {
  state: EstimatedState;
  cx: number;
  cy: number;
  transform: MapTransform;
};

const HEADING_LENGTH_PX = 18;

export function headingEndpoint(
  state: EstimatedState,
  transform: MapTransform,
  lengthPx: number = HEADING_LENGTH_PX,
): WorldPoint {
  const q = state.orientation_xyzw;
  const headingRad = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
  const headingLengthM = lengthPx / Math.abs(transform.scale);
  return worldToMap(
    {
      x: state.position_m.x + Math.cos(headingRad) * headingLengthM,
      y: state.position_m.y + Math.sin(headingRad) * headingLengthM,
    },
    transform,
  );
}

export function ResponderMarker({ state, cx, cy, transform }: Props) {
  const heading = headingEndpoint(state, transform);

  return (
    <g>
      <line className="heading-line" x1={cx} y1={cy} x2={heading.x} y2={heading.y} />
      <circle className="responder-marker" cx={cx} cy={cy} r="10" />
    </g>
  );
}
