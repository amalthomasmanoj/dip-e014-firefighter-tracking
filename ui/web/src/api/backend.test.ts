import { describe, expect, it } from "vitest";
import { backendSourceFromHealth } from "./backend";

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
});
