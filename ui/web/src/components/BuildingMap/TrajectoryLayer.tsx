import { EstimatedState } from "../../types/state";
import { MapTransform, worldToMap } from "../../map/transform";

type Props = {
  states: EstimatedState[];
  transform: MapTransform;
};

export function TrajectoryLayer({ states, transform }: Props) {
  const points = states
    .map((state) => worldToMap({ x: state.position_m.x, y: state.position_m.y }, transform))
    .map((point) => `${point.x},${point.y}`)
    .join(" ");

  return <polyline className="trajectory-line" points={points} fill="none" />;
}

