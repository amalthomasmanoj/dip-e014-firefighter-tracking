import { FormEvent, useEffect, useState } from "react";
import {
  fetchHeartRate,
  heartRateMatchesResponder,
  HeartRateSnapshot,
} from "../api/heartRate";
import { HeartRateAlerts } from "./HeartRateAlerts";
import { HeartRateGraph } from "./HeartRateGraph";

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

export type DesktopHeartRateConfiguration = {
  device: string;
  wearer: string;
  responder_id: string;
  configured: boolean;
};

type Props = {
  selectedResponderId?: string;
  desktopConfiguration?: DesktopHeartRateConfiguration;
  responderIds?: string[];
  onConfigure?: (device: string, wearer: string, responderId: string) => Promise<void>;
};

export function HeartRatePanel({
  selectedResponderId,
  desktopConfiguration,
  responderIds = [],
  onConfigure,
}: Props) {
  const [snapshot, setSnapshot] = useState<HeartRateSnapshot | null>(null);
  const [online, setOnline] = useState(false);
  const [nowUs, setNowUs] = useState(Date.now() * 1000);
  const [device, setDevice] = useState("H808S");
  const [wearer, setWearer] = useState("Firefighter 1");
  const [responderId, setResponderId] = useState("");
  const [setupError, setSetupError] = useState("");
  const [savingSetup, setSavingSetup] = useState(false);
  const responderIdsKey = responderIds.join("\u0000");
  useEffect(() => {
    if (!desktopConfiguration) return;
    setDevice(desktopConfiguration.device || "H808S");
    setWearer(desktopConfiguration.wearer || "Firefighter 1");
    setResponderId(desktopConfiguration.responder_id || responderIds[0] || "");
  }, [
    desktopConfiguration?.device,
    desktopConfiguration?.wearer,
    desktopConfiguration?.responder_id,
    responderIdsKey,
  ]);
  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    let controller: AbortController | undefined;
    async function refresh() {
      setNowUs(Date.now() * 1000);
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

  const assigned = heartRateMatchesResponder(snapshot, selectedResponderId);
  const live = assigned && online && snapshot?.status === "connected" && snapshot.bpm !== null;
  const submitSetup = async (event: FormEvent) => {
    event.preventDefault();
    if (!onConfigure) return;
    setSavingSetup(true);
    setSetupError("");
    try {
      await onConfigure(device, wearer, responderId);
    } catch (error) {
      setSetupError(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingSetup(false);
    }
  };
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
      {!assigned ? (
        <p className="heart-rate-caption">
          No heart-rate strap assigned to this responder.
        </p>
      ) : null}
      {online && snapshot?.device_name ? <p className="heart-rate-caption">{snapshot.device_name}</p> : null}
      {live && snapshot && snapshot.age_s !== null ?
        <p className="heart-rate-caption">Received {snapshot.age_s.toFixed(1)} s ago</p> : null}
      {online && snapshot?.status === "disabled" ?
        <p className="heart-rate-caption">Configure the H808S on the backend to receive readings.</p> : null}
      {online && snapshot?.error ? <p className="heart-rate-caption">{snapshot.error}</p> : null}
      {onConfigure ? (
        <details className="heart-rate-setup" open={!desktopConfiguration?.configured}>
          <summary>Heart-rate sensor setup</summary>
          <form onSubmit={(event) => void submitSetup(event)}>
            <label>
              Device name or identifier
              <input
                value={device}
                maxLength={200}
                placeholder="H808S"
                onChange={(event) => setDevice(event.target.value)}
              />
            </label>
            <label>
              Wearer label
              <input
                value={wearer}
                maxLength={100}
                onChange={(event) => setWearer(event.target.value)}
              />
            </label>
            <label>
              Responder
              <select
                value={responderId}
                required
                onChange={(event) => setResponderId(event.target.value)}
              >
                {responderIds.map((id) => <option key={id} value={id}>{id}</option>)}
              </select>
            </label>
            <div className="heart-rate-setup-actions">
              <button type="submit" disabled={savingSetup || !device.trim() || !responderId}>
                {savingSetup ? "Connecting…" : "Connect / update"}
              </button>
              {desktopConfiguration?.configured ? (
                <button
                  type="button"
                  disabled={savingSetup}
                  onClick={() => {
                    if (!onConfigure) return;
                    setSavingSetup(true);
                    setSetupError("");
                    void onConfigure("", wearer, responderId)
                      .catch((error) => setSetupError(
                        error instanceof Error ? error.message : String(error),
                      ))
                      .finally(() => setSavingSetup(false));
                  }}
                >
                  Disconnect
                </button>
              ) : null}
            </div>
            <p className="heart-rate-caption">
              Wear and moisten the strap first. The app reconnects automatically and remembers this setup.
            </p>
            {setupError ? <p className="hr-warning" role="alert">{setupError}</p> : null}
          </form>
        </details>
      ) : null}
      {assigned ? (
        <HeartRateGraph points={snapshot?.monitor?.history ?? []} nowUs={nowUs} />
      ) : null}
      {assigned && snapshot?.monitor ? (
        <HeartRateAlerts monitor={snapshot.monitor} online={online} />
      ) : null}
    </section>
  );
}
