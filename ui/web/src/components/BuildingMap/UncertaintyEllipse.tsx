import { EstimatedState } from "../../types/state";
import { MapTransform } from "../../map/transform";

type Props = {
  state: EstimatedState;
  cx: number;
  cy: number;
  transform: MapTransform;
};

export function UncertaintyEllipse({ state, cx, cy, transform }: Props) {
  return (
    <ellipse
      className="uncertainty-ellipse"
      cx={cx}
      cy={cy}
      rx={Math.max(4, state.uncertainty.sigma_x_m * transform.scale)}
      ry={Math.max(4, state.uncertainty.sigma_y_m * transform.scale)}
    />
  );
}

