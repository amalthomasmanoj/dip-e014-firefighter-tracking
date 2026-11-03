import { describe, expect, it } from "vitest";
import { graphSegments } from "./HeartRateGraph";

describe("heart-rate trace gaps", () => {
  it("preserves new readings and separates missing periods", () => {
    const points = [
      { timestamp_us: 0, bpm: 80 }, { timestamp_us: 1_000_000, bpm: 81 },
      { timestamp_us: 9_000_000, bpm: 90 },
    ];
    expect(graphSegments(points).map(segment => segment.length)).toEqual([2, 1]);
  });
  it("does not draw backwards after a timestamp reset", () => {
    expect(graphSegments([
      { timestamp_us: 10_000_000, bpm: 80 }, { timestamp_us: 1_000_000, bpm: 81 },
    ])).toHaveLength(2);
    expect(graphSegments([])).toEqual([]);
  });
});
