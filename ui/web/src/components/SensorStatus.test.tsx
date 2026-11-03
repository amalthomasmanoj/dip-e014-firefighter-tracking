import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SensorStatus } from "./SensorStatus";

describe("live anchor resurvey controls", () => {
  it("offers a resurvey after a live map is ready", () => {
    const html = renderToStaticMarkup(
      <SensorStatus
        state={null}
        connected
        source="live"
        liveUwb={{
          source: "live",
          tag_node_id: null,
          tag_present: false,
          latest_timestamp_us: null,
          active_anchor_count: 0,
          ranges: [],
        }}
        anchors={[]}
        usableAnchorCount={0}
        liveAnchorMap={{
          source: "live",
          status: "ready",
          map_version: 1,
          frame: "A1_origin_A2_positive_x",
          reference_anchor_ids: ["A1", "A2", "A3"],
          anchors: [],
          links: [],
          last_error: null,
        }}
        onResurveyAnchors={() => undefined}
      />,
    );

    expect(html).toContain("Resurvey moved anchors");
    expect(html).toContain("Position output pauses");
    expect(html).not.toContain("disabled");
  });

  it("disables restart while a fresh survey is already running", () => {
    const html = renderToStaticMarkup(
      <SensorStatus
        state={null}
        connected
        source="live"
        liveUwb={null}
        anchors={[]}
        usableAnchorCount={0}
        liveAnchorMap={{
          source: "live",
          status: "surveying",
          map_version: 2,
          frame: "A1_origin_A2_positive_x",
          reference_anchor_ids: ["A1", "A2", "A3"],
          anchors: [],
          links: [],
          last_error: null,
        }}
        onResurveyAnchors={() => undefined}
      />,
    );

    expect(html).toContain("Anchor survey in progress");
    expect(html).toContain("disabled");
  });
});
