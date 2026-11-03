import { afterEach, describe, expect, it, vi } from "vitest";
import { backendSourceFromHealth, resurveyLiveAnchorMap } from "./backend";

afterEach(() => vi.unstubAllGlobals());

describe("backend source mapping", () => {
  it("maps UDP to live before any estimator state exists", () => {
    expect(
      backendSourceFromHealth({
        status: "ok",
        source: "udp",
        source_status: "available",
      }),
    ).toBe("live");
  });

  it("keeps simulation and replay modes distinct", () => {
    expect(
      backendSourceFromHealth({
        status: "ok",
        source: "simulation",
        source_status: "available",
      }),
    ).toBe("simulation");
    expect(
      backendSourceFromHealth({
        status: "ok",
        source: "replay",
        source_status: "not_implemented",
      }),
    ).toBe("replay");
  });

  it("starts a real anchor resurvey through the dedicated endpoint", async () => {
    const snapshot = {
      source: "live",
      status: "surveying",
      map_version: 2,
      frame: "A1_origin_A2_positive_x",
      reference_anchor_ids: ["A1", "A2", "A3"],
      anchors: [],
      links: [],
      last_error: null,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => snapshot,
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(resurveyLiveAnchorMap()).resolves.toEqual(snapshot);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/uwb/anchor-map/resurvey",
      { method: "POST" },
    );
  });
});
