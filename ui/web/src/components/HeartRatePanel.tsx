import { useEffect, useState } from "react";
import { fetchHeartRate, HeartRateSnapshot } from "../api/heartRate";

const labels: Record<HeartRateSnapshot["status"], string> = {
  disabled: "Not configured",
  scanning: "Searching for sensor",
  connecting: "Connecting",
  connected: "Live",
  waiting: "Waiting for reading",
  stale: "Reading stale",
  no_contact: "Check strap contact",
  disconnected: "Disconnected",
  error: "Connection problem",
};

export function HeartRatePanel() {
  const [snapshot, setSnapshot] = useState<HeartRateSnapshot | null>(null);
  const [online, setOnline] = useState(false);
  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    let controller: AbortController | undefined;
    async function refresh() {
      controller = new AbortController();
      const timeout = window.setTimeout(() => controller?.abort(), 2_000);
      try {
        const next = await fetchHeartRate(controller.signal);
        if (!disposed) {
          setSnapshot(next);
          setOnline(true);
        }
      } catch {
        if (!disposed) setOnline(false);
      } finally {
        window.clearTimeout(timeout);
        if (!disposed) timer = window.setTimeout(refresh, 500);
      }
    }
    void refresh();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      controller?.abort();
    };
  }, []);

  const live = online && snapshot?.status === "connected" && snapshot.bpm !== null;
  return (
    <section className="side-panel heart-rate-panel" aria-label="Heart rate">
      <div className="heart-rate-heading">
        <h2>Heart rate</h2>
        <span className={live ? "status-pill live" : "status-pill"}>
          {online && snapshot ? labels[snapshot.status] : "Backend offline"}
        </span>
      </div>
      <p className="heart-rate-value">{live ? snapshot.bpm : "--"}<span> BPM</span></p>
      <p className="heart-rate-caption">{snapshot?.wearer ?? "Wearer"} · real sensor</p>
      {online && snapshot?.device_name ? <p className="heart-rate-caption">{snapshot.device_name}</p> : null}
      {live && snapshot.age_s !== null ?
        <p className="heart-rate-caption">Received {snapshot.age_s.toFixed(1)} s ago</p> : null}
      {online && snapshot?.status === "disabled" ?
        <p className="heart-rate-caption">Configure the H808S on the backend to receive readings.</p> : null}
      {online && snapshot?.error ? <p className="heart-rate-caption">{snapshot.error}</p> : null}
    </section>
  );
}
