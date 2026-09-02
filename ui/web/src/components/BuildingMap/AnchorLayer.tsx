import { Anchor } from "../../types/state";
import { MapTransform, worldToMap } from "../../map/transform";

type Props = {
  anchors: Anchor[];
  transform: MapTransform;
};

export function AnchorLayer({ anchors, transform }: Props) {
  return (
    <g>
      {anchors.map((anchor) => {
        const point = worldToMap({ x: anchor.x_m, y: anchor.y_m }, transform);
        return (
          <g key={anchor.anchor_id}>
            <circle className="anchor-dot" cx={point.x} cy={point.y} r="7" />
            <text className="anchor-label" x={point.x + 10} y={point.y - 10}>
              {anchor.anchor_id}
            </text>
          </g>
        );
      })}
    </g>
  );
}

