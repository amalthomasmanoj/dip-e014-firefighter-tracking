import { useEffect, useMemo, useRef, useState } from "react";
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
import { StatePanel } from "./components/StatePanel";
import {
  fallbackDemoState,
  keyboardDemoEnabled,
  moveDemoState,
  stopDemoState,
  toggleDemoCrouch,
} from "./demo/keyboardDemo";
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
  const [demoTrajectory, setDemoTrajectory] = useState<EstimatedState[]>([]);
  const [source, setSource] = useState<BackendSource | null>(null);
  const [liveUwb, setLiveUwb] = useState<LiveUwbSnapshot>(emptyLiveUwbSnapshot);
  const stopTimerRef = useRef<number | null>(null);

  useEffect(() => {
    fetchAnchors()
      .then(setAnchors)
      .catch(() => setAnchors(fallbackAnchors));
  }, []);

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
        return;
      }
      setDemoTrajectory((previous) => (previous.length ? previous : [message.state]));
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
    if (!keyboardDemoEnabled(source)) {
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
  const visualizedState =
    source === "live" && liveUwb.active_anchor_count < 3 ? null : currentState;
  const visibleAnchors = useMemo(() => {
    if (source !== "live") {
      return anchors;
    }
    const activeIds = new Set(liveUwb.ranges.map((range) => range.anchor_id));
    return anchors.filter((anchor) => activeIds.has(anchor.anchor_id));
  }, [anchors, liveUwb.ranges, source]);

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
          <DigitalTwinView
            anchors={visibleAnchors}
            state={visualizedState}
            trajectory={activeTrajectory}
            liveUwb={source === "live" ? liveUwb : null}
          />
          <BuildingMap
            anchors={visibleAnchors}
            currentState={visualizedState}
            trajectory={activeTrajectory}
            liveUwb={source === "live" ? liveUwb : null}
          />
        </div>
        <aside className="sidebar">
          <StatePanel state={visualizedState} />
          <SensorStatus
            state={visualizedState}
            connected={connected}
            source={source}
            liveUwb={source === "live" ? liveUwb : null}
          />
          <ExperimentPlot trajectory={activeTrajectory} />
        </aside>
      </div>
    </main>
  );
}
