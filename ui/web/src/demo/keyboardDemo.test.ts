import { describe, expect, it } from "vitest";
import {
  fallbackDemoState,
  moveDemoState,
  stopDemoState,
  toggleDemoCrouch,
} from "./keyboardDemo";

describe("keyboard demo state", () => {
  it("moves as estimated state without changing the contract shape", () => {
    const moved = moveDemoState(fallbackDemoState(), 1, 0);

    expect(moved.position_m.x).toBeGreaterThan(1);
    expect(moved.activity.motion).toBe("walking");
    expect(moved.status.zupt_active).toBe(false);
  });

  it("toggles crouch and can return to stationary", () => {
    const crouching = toggleDemoCrouch(fallbackDemoState());
    const stopped = stopDemoState(moveDemoState(crouching, 0, 1));

    expect(crouching.activity.posture).toBe("crouching");
    expect(stopped.activity.posture).toBe("crouching");
    expect(stopped.activity.motion).toBe("stationary");
    expect(stopped.status.zupt_active).toBe(true);
  });
});
