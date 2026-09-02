import { EstimatedState } from "../../types/state";

type Props = {
  state: EstimatedState;
  cx: number;
  cy: number;
};

export function ResponderMarker({ state, cx, cy }: Props) {
  const q = state.orientation_xyzw;
  const headingRad = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
  const hx = cx + Math.cos(headingRad) * 18;
  const hy = cy + Math.sin(headingRad) * 18;

  return (
    <g>
      <line className="heading-line" x1={cx} y1={cy} x2={hx} y2={hy} />
      <circle className="responder-marker" cx={cx} cy={cy} r="10" />
    </g>
  );
}

