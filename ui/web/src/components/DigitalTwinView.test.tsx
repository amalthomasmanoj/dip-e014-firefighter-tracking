import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { buildingFootprintFromAnchors } from "./buildingFootprint";
import { DigitalTwinView } from "./DigitalTwinView";

describe("buildingFootprintFromAnchors", () => {
  it("does not invent a building before the anchor map exists", () => {
    expect(buildingFootprintFromAnchors([])).toBeNull();
  });

  it("fits the outline to measured anchor coordinates", () => {
    const footprint = buildingFootprintFromAnchors([
      { anchor_id: "A1", x_m: -1, y_m: 2, z_m: 0 },
      { anchor_id: "A2", x_m: 5, y_m: 2, z_m: 0 },
      { anchor_id: "A3", x_m: 1, y_m: 7, z_m: 0 },
    ]);

    expect(footprint?.minX).toBeCloseTo(-1.6);
    expect(footprint?.maxX).toBeCloseTo(5.6);
    expect(footprint?.minY).toBeCloseTo(1.4);
    expect(footprint?.maxY).toBeCloseTo(7.6);
    expect(footprint?.centerX).toBeCloseTo(2);
    expect(footprint?.centerY).toBeCloseTo(4.5);
    expect(footprint?.width).toBeCloseTo(7.2);
    expect(footprint?.depth).toBeCloseTo(6.2);
  });

  it("exposes zoom, reset, and expanded-view controls", () => {
    const html = renderToStaticMarkup(
      <DigitalTwinView
        anchors={[]}
        state={null}
        trajectory={[]}
        liveUwb={null}
        usableAnchorCount={0}
      />,
    );

    expect(html).toContain('aria-label="Zoom in"');
    expect(html).toContain('aria-label="Zoom out"');
    expect(html).toContain("Reset 3D view");
    expect(html).toContain("Expand Digital Twin");
    expect(html).toContain("Scroll/pinch to zoom");
  });
});
