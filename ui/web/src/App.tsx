import { useEffect, useMemo, useState } from "react";
import { fetchAnchors } from "./api/anchors";
import {
  backendSourceFromHealth,
  fetchBackendHealth,
  fetchLiveUwbRanges,
} from "./api/backend";
import { connectStateStream } from "./api/websocket";
import { BuildingMap } from "./components/BuildingMap/BuildingMap";
import { DigitalTwinView } from "./components/DigitalTwinView";
import { ExperimentPlot } from "./components/ExperimentPlot";
import { SensorStatus } from "./components/SensorStatus";
import { HeartRatePanel } from "./components/HeartRatePanel";
import { StatePanel } from "./components/StatePanel";
import { appendSimulationTracks, fetchSimulation, FirefighterTrack, SimulationSnapshot } from "./api/simulation";
import { SimulationControls } from "./components/SimulationControls";
import {
  Anchor,
  BackendSource,
  EstimatedState,
  LiveUwbSnapshot,
  StateMessage,
} from "./types/state";

const fallbackAnchors: Anchor[] = [
  { anchor_id: "A1", x_m: 0, y_m: 0, z_m: 0 },
  { anchor_id: "A2", x_m: 8, y_m: 0, z_m: 0 },
  { anchor_id: "A3", x_m: 0, y_m: 6, z_m: 0 },
];

const emptyLiveUwbSnapshot: LiveUwbSnapshot = {
  source: "live",
  tag_node_id: null,
  tag_present: false,
  latest_timestamp_us: null,
  active_anchor_count: 0,
  ranges: [],
};

export default function App() {
  const [anchors, setAnchors] = useState<Anchor[]>(fallbackAnchors);
  const [connected, setConnected] = useState(false);
  const [trajectory, setTrajectory] = useState<EstimatedState[]>([]);
  const [simulation, setSimulation] = useState<SimulationSnapshot | null>(null);
  const [tracks, setTracks] = useState<FirefighterTrack[]>([]);
  const [simulationOnline, setSimulationOnline] = useState(false);
  const [selectedTag, setSelectedTag] = useState("sim_tag_10");
  const [source, setSource] = useState<BackendSource | null>(null);
  const [liveUwb, setLiveUwb] = useState<LiveUwbSnapshot>(emptyLiveUwbSnapshot);

  useEffect(() => {
    fetchAnchors()
      .then(setAnchors)
      .catch(() => setAnchors(fallbackAnchors));
  }, []);

  useEffect(() => {
    if (!connected) {
      return;
    }
    fetchAnchors().then(setAnchors).catch(() => undefined);
  }, [connected]);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      fetchBackendHealth()
        .then((health) => {
          if (!cancelled) {
            setSource(backendSourceFromHealth(health));
          }
        })
        .catch(() => undefined);
    };
    refresh();
    const interval = window.setInterval(refresh, 1_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let disposed = false;
    let retryTimer: number | null = null;
    let socket: WebSocket | null = null;

    const handleMessage = (message: StateMessage) => {
      setSource(message.source);
      if (message.source === "live") {
        setTrajectory((previous) => [...previous.slice(-180), message.state]);
      }
    };

    const openSocket = () => {
      socket = connectStateStream(handleMessage, (isConnected) => {
        setConnected(isConnected);
        if (!isConnected && !disposed && retryTimer === null) {
          retryTimer = window.setTimeout(() => {
            retryTimer = null;
            openSocket();
          }, 1_000);
        }
      });
    };

    openSocket();
    return () => {
      disposed = true;
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
      }
      socket?.close();
    };
  }, []);

  useEffect(() => {
    if (source !== "live") {
      setLiveUwb(emptyLiveUwbSnapshot);
      return;
    }

    let cancelled = false;
    const refresh = () => {
      fetchLiveUwbRanges()
        .then((snapshot) => {
          if (!cancelled) {
            setLiveUwb(snapshot);
          }
        })
        .catch(() => undefined);
    };
    refresh();
    const interval = window.setInterval(refresh, 250);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [source]);

  useEffect(() => {
    if (source !== "simulation") return;
    let disposed = false;
    let timer: number | undefined;
    let lastTimestamp = -1;
    let lastAdvance = performance.now();
    async function refresh() {
      try {
        const snapshot = await fetchSimulation();
        if (disposed) return;
        if (snapshot.timestamp_us !== lastTimestamp) {
          lastTimestamp = snapshot.timestamp_us;
          lastAdvance = performance.now();
        }
        setSimulationOnline(performance.now() - lastAdvance < 1500);
        setSimulation(snapshot);
        setTracks((previous) => appendSimulationTracks(previous, snapshot));
      } catch {
        if (!disposed) setSimulationOnline(false);
      } finally {
        if (!disposed) timer = window.setTimeout(refresh, 100);
      }
    }
    void refresh();
    return () => { disposed = true; window.clearTimeout(timer); };
  }, [source]);

  const activeAnchors = source === "simulation" && simulation ? simulation.anchors : anchors;
  const activeTracks = source === "simulation" ? tracks : undefined;
  const selectedTrack = tracks.find((tag) => tag.node_id === selectedTag);
  const activeTrajectory = source === "simulation" ? selectedTrack?.trajectory ?? [] : trajectory;
  const currentState = source === "simulation" ? selectedTrack?.state ?? null : activeTrajectory.at(-1) ?? null;
  const displayConnected = source === "simulation" ? simulationOnline : connected;
  const usableLiveAnchorCount = useMemo(() => {
    const configuredIds = new Set(anchors.map((anchor) => anchor.anchor_id));
    return liveUwb.ranges.filter((range) => configuredIds.has(range.anchor_id)).length;
  }, [anchors, liveUwb.ranges]);
  const visualizedState =
    source === "live" &&
    (usableLiveAnchorCount < 3 ||
      (currentState?.status.active_anchor_count ?? 0) < 3)
      ? null
      : currentState;

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>E014 Firefighter Tracking</h1>
          <p>UWB + foot IMU/ZUPT indoor trajectory estimation</p>
        </div>
        <span className={displayConnected ? "status-pill live" : "status-pill"}>{displayConnected ? source === "simulation" ? "SIMULATION" : "LIVE" : "OFFLINE"}</span>
      </header>
      <div className="workspace">
        <div className="main-views">
          <DigitalTwinView
            anchors={activeAnchors}
            state={visualizedState}
            trajectory={activeTrajectory}
            liveUwb={source === "live" ? liveUwb : null}
            usableAnchorCount={usableLiveAnchorCount}
            firefighters={activeTracks}
            anchorLinks={source === "simulation" && simulationOnline ? simulation?.anchor_links : undefined}
          />
          <BuildingMap
            anchors={activeAnchors}
            currentState={visualizedState}
            trajectory={activeTrajectory}
            liveUwb={source === "live" ? liveUwb : null}
            usableAnchorCount={usableLiveAnchorCount}
            firefighters={activeTracks}
            anchorLinks={source === "simulation" && simulationOnline ? simulation?.anchor_links : undefined}
          />
        </div>
        <aside className="sidebar">
          {source === "simulation" ? <>
            <SimulationControls snapshot={simulation} online={simulationOnline} />
            <section className="side-panel">
              <label htmlFor="inspected-firefighter">Inspect firefighter</label>
              <select id="inspected-firefighter" value={selectedTag} onChange={(event) => setSelectedTag(event.target.value)}>
                {tracks.map((tag) => <option key={tag.node_id} value={tag.node_id}>{tag.label}</option>)}
              </select>
            </section>
          </> : null}
          <HeartRatePanel selectedResponderId={source === "simulation" ? selectedTag : undefined} />
          <StatePanel state={visualizedState} />
          <SensorStatus
            state={visualizedState}
            connected={displayConnected}
            source={source}
            liveUwb={source === "live" ? liveUwb : null}
            anchors={activeAnchors}
            usableAnchorCount={usableLiveAnchorCount}
          />
          <ExperimentPlot trajectory={activeTrajectory} />
        </aside>
      </div>
    </main>
  );
}
