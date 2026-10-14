import { Anchor, EstimatedState, UwbRangeReading } from "../../types/state";
import { MapTransform, worldToMap } from "../../map/transform";

type Props = {
  anchors: Anchor[];
  state: EstimatedState | null;
  ranges: UwbRangeReading[];
  transform: MapTransform;
};

export function UwbRangeLayer({ anchors, state, ranges, transform }: Props) {
  const anchorsById = new Map(anchors.map((anchor) => [anchor.anchor_id, anchor]));

  if (!state) {
    return (
      <g>
        {ranges.map((range) => {
          const anchor = anchorsById.get(range.anchor_id);
          if (!anchor) {
            return null;
          }
          const point = worldToMap({ x: anchor.x_m, y: anchor.y_m }, transform);
          return (
            <g key={range.anchor_id}>
              <circle
                className="uwb-range-circle"
                cx={point.x}
                cy={point.y}
                r={range.range_m * Math.abs(transform.scale)}
              />
              <text className="uwb-range-label" x={point.x + 12} y={point.y + 20}>
                {range.range_m.toFixed(2)} m
              </text>
            </g>
          );
        })}
      </g>
    );
  }

  const tag = worldToMap({ x: state.position_m.x, y: state.position_m.y }, transform);
  return (
    <g>
      {ranges.map((range) => {
        const anchor = anchorsById.get(range.anchor_id);
        if (!anchor) {
          return null;
        }
        const point = worldToMap({ x: anchor.x_m, y: anchor.y_m }, transform);
        return (
          <g key={range.anchor_id}>
            <line
              className="uwb-range-line"
              x1={tag.x}
              y1={tag.y}
              x2={point.x}
              y2={point.y}
            />
            <text
              className="uwb-range-label"
              x={(tag.x + point.x) / 2 + 6}
              y={(tag.y + point.y) / 2 - 6}
            >
              {range.range_m.toFixed(2)} m
            </text>
          </g>
        );
      })}
    </g>
  );
}
