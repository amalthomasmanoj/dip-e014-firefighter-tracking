import { FormEvent, useEffect, useRef, useState } from "react";
import { acknowledgeAlert, AlertSettings, HeartRateAlert, HeartRateMonitor, saveAlertSettings } from "../api/heartRate";

const alertLabels = {
  high: "Sustained high HR — check responder",
  low: "Sustained low HR — check responder",
  signal_loss: "HR signal unavailable — check sensor/link",
};
const numericFields: { key: Exclude<keyof AlertSettings, "enabled">; label: string; min: number; max: number }[] = [
  { key: "low_bpm", label: "Low limit (BPM)", min: 1, max: 299 },
  { key: "high_bpm", label: "High limit (BPM)", min: 2, max: 300 },
  { key: "low_duration_s", label: "Low duration (s)", min: 1, max: 600 },
  { key: "high_duration_s", label: "High duration (s)", min: 1, max: 600 },
  { key: "hysteresis_bpm", label: "Recovery margin (BPM)", min: 0, max: 50 },
  { key: "signal_loss_s", label: "Signal-loss delay (s)", min: 5, max: 120 },
];

function eventDetail(event: HeartRateAlert): string {
  const reading = event.bpm === null ? "" : ` · ${event.bpm} BPM`;
  const ending = event.ended_us === null ? "active" : ({
    reading_recovered: "reading recovered", data_unavailable: "data became unavailable",
    settings_changed: "settings changed",
  }[event.end_reason ?? ""] ?? "ended");
  return `${new Date(event.started_us / 1000).toLocaleTimeString()}${reading} · ${Math.round(event.duration_s)} s at trigger · ${ending}`;
}

export function HeartRateAlerts({ monitor, online }: { monitor: HeartRateMonitor; online: boolean }) {
  const [draft, setDraft] = useState<AlertSettings>(monitor.settings);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [sound, setSound] = useState(false);
  const audio = useRef<AudioContext | null>(null);
  const serverKey = JSON.stringify(monitor.settings);
  useEffect(() => { setDraft(monitor.settings); }, [serverKey]);
  useEffect(() => () => { void audio.current?.close(); }, []);

  const active = monitor.active;
  useEffect(() => {
    if (!sound || !online || !active || active.acknowledged) return;
    const beep = () => {
      const ctx = audio.current;
      if (!ctx || ctx.state !== "running") return;
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      oscillator.frequency.value = 660;
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      oscillator.connect(gain); gain.connect(ctx.destination);
      oscillator.start(); oscillator.stop(ctx.currentTime + 0.25);
    };
    beep();
    const timer = window.setInterval(beep, 5_000);
    return () => window.clearInterval(timer);
  }, [sound, online, active?.id, active?.acknowledged]);

  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try { await saveAlertSettings(draft); }
    catch (failure) { setError((failure as Error).message); }
    finally { setSaving(false); }
  }
  async function toggleSound() {
    try {
      if (!sound) {
        audio.current ??= new AudioContext();
        await audio.current.resume();
        if (audio.current.state !== "running") throw new Error("Browser audio is unavailable.");
      }
      setSound(!sound);
    } catch (failure) { setError((failure as Error).message); }
  }
  const pending = monitor.pending;
  const remaining = pending ? Math.max(0, (pending.kind === "high" ?
    monitor.settings.high_duration_s : monitor.settings.low_duration_s) - pending.elapsed_s) : 0;
  return <div className="hr-alerts">
    <h3>Responder-check alerts</h3>
    <p className="heart-rate-caption">Prototype thresholds; not a fainting detector or medical diagnosis.</p>
    {!online ? <p className="hr-warning" role="status">Backend offline — monitoring status unknown.</p> :
      active ? <div className="hr-alarm" role="alert">
        <strong>{alertLabels[active.kind]}</strong>
        <p>{eventDetail(active)}</p>
        <button disabled={active.acknowledged} onClick={() => {
          void acknowledgeAlert(active.id).catch(() => setError("Could not acknowledge alert."));
        }}>{active.acknowledged ? "Acknowledged" : "Acknowledge / silence"}</button>
      </div> : pending ? <p className="hr-warning" role="status">
        {pending.kind === "high" ? "High" : "Low"} HR · {Math.ceil(remaining)} s of new valid readings still required
      </p> : <p className="heart-rate-caption">{monitor.settings.enabled ? "Monitoring enabled" : "Alerts disabled"}</p>}
    <button type="button" onClick={() => void toggleSound()}>{sound ? "Mute browser sound" : "Enable browser sound"}</button>
    <details>
      <summary>Configure thresholds</summary>
      <form onSubmit={event => void submit(event)}>
        <p className="heart-rate-caption">Initial values are examples, not validated danger limits. Settings apply to this backend and reset on restart.</p>
        <label className="hr-checkbox"><input type="checkbox" checked={draft.enabled}
          onChange={e => setDraft({ ...draft, enabled: e.target.checked })} />Enable monitoring</label>
        <div className="hr-settings-grid">{numericFields.map(field => <label key={field.key}>
          {field.label}<input type="number" min={field.min} max={field.max} step="1" required
            value={Number.isFinite(draft[field.key]) ? draft[field.key] : ""}
            onChange={e => setDraft({ ...draft, [field.key]: e.target.valueAsNumber })} />
        </label>)}</div>
        <button type="submit" disabled={saving || !online}>{saving ? "Saving…" : "Apply settings"}</button>
      </form>
    </details>
    {error ? <p className="hr-warning" role="alert">{error}</p> : null}
    <p className="heart-rate-caption">Backend evaluates alerts while running. Sound needs this dashboard open and browser audio allowed. Check person/sensor when alerted; missing HR does not establish cardiac arrest.</p>
    <details><summary>Event history ({monitor.events.length})</summary>
      {monitor.events.length ? <ol className="hr-events">{monitor.events.slice(0, 20).map(event =>
        <li key={event.id}><strong>{alertLabels[event.kind]}</strong><br />{eventDetail(event)}
          {event.acknowledged ? " · acknowledged" : ""}</li>)}</ol> : <p className="heart-rate-caption">No events this session.</p>}
    </details>
  </div>;
}
