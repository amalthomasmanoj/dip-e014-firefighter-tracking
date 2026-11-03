import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { HeartRateMonitor } from "../api/heartRate";
import { HeartRateAlerts } from "./HeartRateAlerts";
import { HeartRateGraph } from "./HeartRateGraph";
import { HeartRatePanel } from "./HeartRatePanel";

const base: HeartRateMonitor = {
  settings: { enabled: true, low_bpm: 50, high_bpm: 160, low_duration_s: 30,
    high_duration_s: 30, hysteresis_bpm: 5, signal_loss_s: 5 },
  pending: null, active: null, events: [], history: [],
};
describe("heart-rate monitor presentation", () => {
  it("shows a pending countdown and the prototype limitation", () => {
    const html = renderToStaticMarkup(<HeartRateAlerts online monitor={{ ...base,
      pending: { kind: "high", elapsed_s: 12 } }} />);
    expect(html).toContain("18 s of new valid readings still required");
    expect(html).toContain("not a fainting detector");
  });
  it("distinguishes signal loss from a low-heart-rate event", () => {
    const html = renderToStaticMarkup(<HeartRateAlerts online monitor={{ ...base,
      active: { id: 1, kind: "signal_loss", bpm: null, started_us: 1_000_000,
        duration_s: 5, acknowledged: false, ended_us: null, end_reason: null } }} />);
    expect(html).toContain("HR signal unavailable");
    expect(html).not.toContain("Sustained low HR");
    expect(html).toContain("Acknowledge / silence");
  });
  it("never claims monitoring is live when the backend is offline", () => {
    const html = renderToStaticMarkup(<HeartRateAlerts online={false} monitor={base} />);
    expect(html).toContain("monitoring status unknown");
    expect(html).not.toContain("Monitoring enabled");
  });
  it("shows a waiting graph without fabricating sensor values", () => {
    const html = renderToStaticMarkup(<HeartRateGraph points={[]} nowUs={300_000_000} />);
    expect(html).toContain("Waiting for valid readings");
    expect(html).not.toContain("polyline");
  });
  it("offers saved desktop sensor setup without a terminal", () => {
    const html = renderToStaticMarkup(<HeartRatePanel
      desktopConfiguration={{
        device: "",
        wearer: "Firefighter 1",
        responder_id: "firefighter_1",
        configured: false,
      }}
      responderIds={["firefighter_1"]}
      onConfigure={async () => undefined}
    />);
    expect(html).toContain("Heart-rate sensor setup");
    expect(html).toContain("Connect / update");
    expect(html).toContain("firefighter_1");
  });
});
