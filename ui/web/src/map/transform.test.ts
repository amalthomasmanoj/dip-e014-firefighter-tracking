import { describe, expect, it } from "vitest";
import { mapToWorld, worldToMap } from "./transform";

describe("map transform", () => {
  it("applies translation", () => {
    expect(worldToMap({ x: 1, y: 2 }, {
      scale: 1,
      rotationRad: 0,
      translateX: 10,
      translateY: 20,
    })).toEqual({ x: 11, y: 18 });
  });

  it("applies scale with world y up and SVG y down", () => {
    expect(worldToMap({ x: 2, y: 3 }, {
      scale: 4,
      rotationRad: 0,
      translateX: 0,
      translateY: 40,
    })).toEqual({ x: 8, y: 28 });
  });

  it("applies rotation in the documented world frame", () => {
    const point = worldToMap({ x: 1, y: 0 }, {
      scale: 1,
      rotationRad: Math.PI / 2,
      translateX: 0,
      translateY: 0,
    });

    expect(point.x).toBeCloseTo(0);
    expect(point.y).toBeCloseTo(-1);
  });

  it("round trips map and world coordinates", () => {
    const transform = {
      scale: 12,
      rotationRad: Math.PI / 6,
      translateX: 100,
      translateY: 220,
    };
    const world = { x: 3.5, y: 1.25 };
    const roundTrip = mapToWorld(worldToMap(world, transform), transform);

    expect(roundTrip.x).toBeCloseTo(world.x);
    expect(roundTrip.y).toBeCloseTo(world.y);
  });

  it("rejects non-finite input", () => {
    expect(() => worldToMap({ x: Number.NaN, y: 0 }, {
      scale: 1,
      rotationRad: 0,
      translateX: 0,
      translateY: 0,
    })).toThrow();
  });
});
