import { afterEach, describe, expect, it, vi } from "vitest";
import { fallbackDemoState } from "../demo/keyboardDemo";
import { appendSimulationTracks, sendSimulationCommand, SimulationSnapshot } from "./simulation";

function snapshot(timestamp = 100): SimulationSnapshot {
  return {
    source: "simulation", timestamp_us: timestamp, map_version: 1,
    frame: "fixed_world", geometry_valid: true, anchors: [], anchor_links: [],
    firefighters: ["sim_tag_10", "sim_tag_11"].map((node_id, index) => ({
      node_id, label: node_id, ranges: [],
      state: { ...fallbackDemoState(), timestamp_us: timestamp, position_m: { x: index * 4, y: 1, z: 0 } },
    })),
  };
}
afterEach(() => vi.unstubAllGlobals());
describe("simulation tracks", () => {
  it("keeps independent trails by tag ID even if response order changes", () => {
    const first = appendSimulationTracks([], snapshot());
    const next = snapshot(200);
    next.firefighters.reverse();
    const tracks = appendSimulationTracks(first, next);
    expect(tracks[0].node_id).toBe("sim_tag_11");
    expect(tracks[0].trajectory.map((state) => state.position_m.x)).toEqual([4, 4]);
    expect(tracks[1].trajectory.map((state) => state.position_m.x)).toEqual([0, 0]);
    expect(appendSimulationTracks(tracks, next)[0].trajectory).toHaveLength(2);
  });
  it("bounds history and resets after a backend restart", () => {
    let tracks = appendSimulationTracks([], snapshot(100));
    for (let timestamp = 200; timestamp < 25000; timestamp += 100) {
      tracks = appendSimulationTracks(tracks, snapshot(timestamp));
    }
    expect(tracks[0].trajectory).toHaveLength(180);
    expect(appendSimulationTracks(tracks, snapshot(100))[0].trajectory).toHaveLength(1);
  });
  it("keeps the trail but exposes unresolved state on degenerate geometry", () => {
    const first = appendSimulationTracks([], snapshot());
    const unresolved = snapshot(200);
    unresolved.firefighters[0].state = null;
    const tracks = appendSimulationTracks(first, unresolved);
    expect(tracks[0].state).toBeNull();
    expect(tracks[0].trajectory).toHaveLength(1);
    expect(tracks[1].trajectory).toHaveLength(2);
  });
  it("sends movement to the backend and surfaces rejected commands", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    await sendSimulationCommand({ kind: "anchor", node_id: "A3", dx_m: 0.2 });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ kind: "anchor", node_id: "A3", dx_m: 0.2 });
    fetchMock.mockResolvedValue({ ok: false, status: 409 });
    await expect(sendSimulationCommand({ kind: "anchor", node_id: "A3" })).rejects.toThrow("409");
  });
});
