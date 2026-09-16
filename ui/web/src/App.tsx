import { useEffect, useMemo, useRef, useState } from "react";
import { fetchAnchors } from "./api/anchors";
import { connectStateStream } from "./api/websocket";
import { BuildingMap } from "./components/BuildingMap/BuildingMap";
import { DigitalTwinView } from "./components/DigitalTwinView";
import { ExperimentPlot } from "./components/ExperimentPlot";
import { SensorStatus } from "./components/SensorStatus";
import { StatePanel } from "./components/StatePanel";
import {
  fallbackDemoState,
  moveDemoState,
  stopDemoState,
  toggleDemoCrouch,
} from "./demo/keyboardDemo";
import { Anchor, EstimatedState } from "./types/state";

const fallbackAnchors: Anchor[] = [
  { anchor_id: "A1", x_m: 0, y_m: 0, z_m: 0 },
  { anchor_id: "A2", x_m: 8, y_m: 0, z_m: 0 },
  { anchor_id: "A3", x_m: 0, y_m: 6, z_m: 0 },
];

export default function App() {
  const [anchors, setAnchors] = useState<Anchor[]>(fallbackAnchors);
  const [connected, setConnected] = useState(false);
  const [trajectory, setTrajectory] = useState<EstimatedState[]>([]);
  const [demoTrajectory, setDemoTrajectory] = useState<EstimatedState[]>([]);
  const [source, setSource] = useState<"simulation" | "live" | "replay" | null>(null);
  const stopTimerRef = useRef<number | null>(null);

  useEffect(() => {
    fetchAnchors()
      .then(setAnchors)
      .catch(() => setAnchors(fallbackAnchors));
  }, []);

  useEffect(() => {
    const socket = connectStateStream((message) => {
      setSource(message.source);
      if (message.source === "live") {
        setTrajectory((previous) => [...previous.slice(-180), message.state]);
        return;
      }

      setDemoTrajectory((previous) => (previous.length ? previous : [message.state]));
    }, setConnected);
    return () => socket.close();
  }, []);

  useEffect(() => {
    if (source === "live") {
      return;
    }

    function updateDemoState(updater: (state: EstimatedState) => EstimatedState) {
      setDemoTrajectory((previous) => {
        const current = previous.at(-1) ?? fallbackDemoState();
        const next = updater(current);
        return [...previous.slice(-180), next];
      });
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }

      const movementByKey: Record<string, { dx: number; dy: number } | undefined> = {
        ArrowUp: { dx: 0, dy: 1 },
        ArrowDown: { dx: 0, dy: -1 },
        ArrowLeft: { dx: -1, dy: 0 },
        ArrowRight: { dx: 1, dy: 0 },
      };
      const movementByCode: Record<string, { dx: number; dy: number } | undefined> = {
        Numpad8: { dx: 0, dy: 1 },
        Numpad2: { dx: 0, dy: -1 },
        Numpad4: { dx: -1, dy: 0 },
        Numpad6: { dx: 1, dy: 0 },
      };
      const movement = movementByKey[event.key] ?? movementByCode[event.code];

      if (movement) {
        event.preventDefault();
        updateDemoState((state) => moveDemoState(state, movement.dx, movement.dy));
        if (stopTimerRef.current !== null) {
          window.clearTimeout(stopTimerRef.current);
        }
        stopTimerRef.current = window.setTimeout(() => {
          updateDemoState(stopDemoState);
        }, 180);
      }

      if (event.key.toLowerCase() === "c") {
        event.preventDefault();
        updateDemoState(toggleDemoCrouch);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (stopTimerRef.current !== null) {
        window.clearTimeout(stopTimerRef.current);
        stopTimerRef.current = null;
      }
    };
  }, [source]);

  const activeTrajectory = source === "live" ? trajectory : demoTrajectory;
  const currentState = useMemo(() => activeTrajectory.at(-1) ?? null, [activeTrajectory]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>E014 Firefighter Tracking</h1>
          <p>UWB + foot IMU/ZUPT indoor trajectory estimation</p>
        </div>
        <span className={connected ? "status-pill live" : "status-pill"}>{connected ? "LIVE" : "OFFLINE"}</span>
      </header>
      <div className="workspace">
        <div className="main-views">
          <DigitalTwinView anchors={anchors} state={currentState} trajectory={activeTrajectory} />
          <BuildingMap anchors={anchors} currentState={currentState} trajectory={activeTrajectory} />
        </div>
        <aside className="sidebar">
          <StatePanel state={currentState} />
          <SensorStatus state={currentState} connected={connected} />
          <ExperimentPlot trajectory={activeTrajectory} />
        </aside>
      </div>
    </main>
  );
}
