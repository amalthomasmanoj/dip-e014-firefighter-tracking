import { useEffect, useMemo, useState } from "react";
import { fetchAnchors } from "./api/anchors";
import { connectStateStream } from "./api/websocket";
import { BuildingMap } from "./components/BuildingMap/BuildingMap";
import { ExperimentPlot } from "./components/ExperimentPlot";
import { SensorStatus } from "./components/SensorStatus";
import { StatePanel } from "./components/StatePanel";
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

  useEffect(() => {
    fetchAnchors()
      .then(setAnchors)
      .catch(() => setAnchors(fallbackAnchors));
  }, []);

  useEffect(() => {
    const socket = connectStateStream((message) => {
      setTrajectory((previous) => [...previous.slice(-180), message.state]);
    }, setConnected);
    return () => socket.close();
  }, []);

  const currentState = useMemo(() => trajectory.at(-1) ?? null, [trajectory]);

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
        <BuildingMap anchors={anchors} currentState={currentState} trajectory={trajectory} />
        <aside className="sidebar">
          <StatePanel state={currentState} />
          <SensorStatus state={currentState} connected={connected} />
          <ExperimentPlot trajectory={trajectory} />
        </aside>
      </div>
    </main>
  );
}
