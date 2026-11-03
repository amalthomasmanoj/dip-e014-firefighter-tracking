import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SimulationSnapshot } from "../api/simulation";
import { SimulationControls, simulationFirefighterId } from "./SimulationControls";

const snapshot: SimulationSnapshot = {
  source: "simulation",
  timestamp_us: 100_000,
  map_version: 1,
  frame: "fixed_world",
  geometry_valid: true,
  anchors: [],
  firefighters: [
    { node_id: "sim_tag_10", label: "Firefighter 1", state: null, ranges: [] },
    { node_id: "sim_tag_11", label: "Firefighter 2", state: null, ranges: [] },
  ],
  anchor_links: [],
};

describe("simulation control target", () => {
  it("identifies only firefighter targets for the inspected state", () => {
    expect(simulationFirefighterId("firefighter:sim_tag_11")).toBe("sim_tag_11");
    expect(simulationFirefighterId("anchor:A2")).toBeNull();
  });

  it("renders Firefighter 2 as the controlled target", () => {
    const html = renderToStaticMarkup(
      <SimulationControls
        snapshot={snapshot}
        online
        target="firefighter:sim_tag_11"
        onTargetChange={() => undefined}
      />,
    );
    expect(html).toContain('<option value="firefighter:sim_tag_11" selected="">Firefighter 2</option>');
    expect(html).toContain("Control");
  });
});
