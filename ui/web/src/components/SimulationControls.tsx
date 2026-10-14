import { useCallback, useEffect, useRef, useState } from "react";
import { SimulationSnapshot, sendSimulationCommand } from "../api/simulation";

type Props = { snapshot: SimulationSnapshot | null; online: boolean };

export function SimulationControls({ snapshot, online }: Props) {
  const [target, setTarget] = useState("firefighter:sim_tag_10");
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const separator = target.indexOf(":");
  const kind = target.slice(0, separator) as "firefighter" | "anchor";
  const nodeId = target.slice(separator + 1);
  const command = useCallback(async (dx = 0, dy = 0, crouch = false) => {
    if (!online || pending.current) return;
    pending.current = true;
    try {
      await sendSimulationCommand({
        kind, node_id: nodeId, dx_m: dx, dy_m: dy,
        action: crouch ? "toggle_crouch" : "move",
      });
      setError(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Command failed");
    } finally {
      pending.current = false;
    }
  }, [kind, nodeId, online]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey ||
          (event.target instanceof HTMLElement &&
           (event.target.closest("input, select, textarea, button") || event.target.isContentEditable))) return;
      const moves: Record<string, [number, number]> = {
        ArrowUp: [0, 0.2], ArrowDown: [0, -0.2],
        ArrowLeft: [-0.2, 0], ArrowRight: [0.2, 0],
        Numpad8: [0, 0.2], Numpad2: [0, -0.2],
        Numpad4: [-0.2, 0], Numpad6: [0.2, 0],
      };
      const delta = moves[event.key] ?? moves[event.code];
      if (delta) {
        event.preventDefault();
        void command(...delta);
      } else if (event.key.toLowerCase() === "c" && kind === "firefighter" && !event.repeat) {
        event.preventDefault();
        void command(0, 0, true);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [command, kind]);

  return <section className="side-panel simulation-controls">
    <h2>Simulation controls</h2>
    <p>Two firefighters · movable anchors</p>
    <label htmlFor="simulation-target">Move</label>
    <select id="simulation-target" value={target} onChange={(event) => setTarget(event.target.value)}>
      {(snapshot?.firefighters ?? []).map((tag) =>
        <option key={tag.node_id} value={`firefighter:${tag.node_id}`}>{tag.label}</option>)}
      {(snapshot?.anchors ?? []).map((anchor) =>
        <option key={anchor.anchor_id} value={`anchor:${anchor.anchor_id}`}>Anchor {anchor.anchor_id}</option>)}
    </select>
    <div className="movement-buttons">
      <button disabled={!online} onClick={() => void command(-0.2, 0)} aria-label="Move left">←</button>
      <button disabled={!online} onClick={() => void command(0, 0.2)} aria-label="Move up">↑</button>
      <button disabled={!online} onClick={() => void command(0, -0.2)} aria-label="Move down">↓</button>
      <button disabled={!online} onClick={() => void command(0.2, 0)} aria-label="Move right">→</button>
    </div>
    {kind === "firefighter" ? <button disabled={!online} onClick={() => void command(0, 0, true)}>Toggle crouch (C)</button> : null}
    <p>Arrow keys / numpad move the selected node by 0.2 m. Click the map to leave the selector, then use keys.</p>
    <p className="simulation-note">Simulated pair exchanges at 10 Hz. Coordinates stay in a fixed world frame; hardware support is unconfirmed.</p>
    {!online ? <p role="status">Simulation disconnected — controls paused.</p> : null}
    {snapshot && !snapshot.geometry_valid ? <p role="alert">Anchor geometry cannot resolve a position. Move anchors apart into a triangle.</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    <h2>Anchor communication {online ? "· active" : "· stale"}</h2>
    <ul className="range-list">
      {(snapshot?.anchor_links ?? []).map((link) => <li key={`${link.initiator_id}-${link.responder_id}`}>
        <span>{link.initiator_id} ↔ {link.responder_id}<small>exchange #{link.sequence_number}</small></span>
        <strong>{link.raw_range_m.toFixed(2)} m</strong>
      </li>)}
    </ul>
    <p>Anchor map version {snapshot?.map_version ?? "—"}</p>
  </section>;
}
