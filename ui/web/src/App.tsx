import { useEffect, useMemo, useRef, useState } from "react";
import { fetchAnchors } from "./api/anchors";
import {
  backendSourceFromHealth,
  alignResponderHeading,
  fetchBackendHealth,
  fetchLiveAnchorMap,
  fetchLiveSensorStatus,
  fetchLiveUwbRanges,
} from "./api/backend";
import { connectStateStream } from "./api/websocket";
import { backendHttpUrl, isAndroidViewer, savedServerUrl, saveServerUrl } from "./api/server";
import {
  appendLiveTrack,
  detectedLiveAnchors,
  LiveFirefighterTrack,
  pruneStaleLiveTracks,
} from "./api/live";
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
  LiveUwbSnapshot,
  LiveAnchorMapSnapshot,
  LiveSensorStatus,
  StateMessage,
} from "./types/state";

type DesktopHostStatus = {
  mode: "simulation" | "udp";
  running: boolean;
  status: string;
  local_url: string;
  public_url: string | null;
};

type DesktopHostApi = {
  get_status: () => Promise<DesktopHostStatus>;
  switch_mode: (mode: "simulation" | "udp") => Promise<DesktopHostStatus>;
  share_publicly: () => Promise<DesktopHostStatus>;
  open_logs: () => Promise<void>;
};

declare global {
  interface Window {
    pywebview?: { api: DesktopHostApi };
  }
}

const emptyLiveUwbSnapshot: LiveUwbSnapshot = {
  source: "live",
  tag_node_id: null,
  tag_present: false,
  latest_timestamp_us: null,
  active_anchor_count: 0,
  ranges: [],
};

const emptyLiveAnchorMap: LiveAnchorMapSnapshot = {
  source: "live",
  status: "surveying",
  map_version: 0,
  frame: "A1_origin_A2_positive_x",
  reference_anchor_ids: ["A1", "A2", "A3"],
  anchors: [],
  links: [],
  last_error: null,
};

export default function App() {
  const [anchors, setAnchors] = useState<Anchor[]>([]);
  const [connected, setConnected] = useState(false);
  const [simulation, setSimulation] = useState<SimulationSnapshot | null>(null);
  const [tracks, setTracks] = useState<FirefighterTrack[]>([]);
  const [liveTracks, setLiveTracks] = useState<LiveFirefighterTrack[]>([]);
  const [simulationOnline, setSimulationOnline] = useState(false);
  const [selectedTag, setSelectedTag] = useState("sim_tag_10");
  const [selectedLiveTag, setSelectedLiveTag] = useState("");
  const [source, setSource] = useState<BackendSource | null>(null);
  const [liveUwb, setLiveUwb] = useState<LiveUwbSnapshot>(emptyLiveUwbSnapshot);
  const [liveAnchorMap, setLiveAnchorMap] = useState<LiveAnchorMapSnapshot>(emptyLiveAnchorMap);
  const [liveSensorStatus, setLiveSensorStatus] = useState<LiveSensorStatus | null>(null);
  const liveMapVersionRef = useRef(0);
  const androidViewer = isAndroidViewer();
  const desktopApp = new URLSearchParams(window.location.search).get("desktop") === "1";
  const [desktopHost, setDesktopHost] = useState<DesktopHostStatus | null>(null);
  const [desktopAction, setDesktopAction] = useState("");
  const [desktopError, setDesktopError] = useState("");
  const [showServerSetup, setShowServerSetup] = useState(
    androidViewer && savedServerUrl() === null,
  );
  const [serverUrlInput, setServerUrlInput] = useState(savedServerUrl() ?? "");
  const [serverUrlError, setServerUrlError] = useState("");

  const applyServerUrl = () => {
    try {
      saveServerUrl(serverUrlInput);
      window.location.reload();
    } catch (error) {
      setServerUrlError(error instanceof Error ? error.message : "Invalid server URL.");
    }
  };

  useEffect(() => {
    if (!desktopApp) return;
    let disposed = false;
    const refresh = () => {
      const api = window.pywebview?.api;
      if (!api) return;
      api.get_status()
        .then((status) => {
          if (!disposed) setDesktopHost(status);
        })
        .catch(() => undefined);
    };
    const ready = () => refresh();
    window.addEventListener("pywebviewready", ready);
    refresh();
    const interval = window.setInterval(refresh, 1_000);
    return () => {
      disposed = true;
      window.removeEventListener("pywebviewready", ready);
      window.clearInterval(interval);
    };
  }, [desktopApp]);

  const switchDesktopMode = async (mode: "simulation" | "udp") => {
    const api = window.pywebview?.api;
    if (!api || desktopAction) return;
    setDesktopAction("Switching data source…");
    setDesktopError("");
    try {
      setDesktopHost(await api.switch_mode(mode));
      setTracks([]);
      setLiveTracks([]);
    } catch (error) {
      setDesktopError(error instanceof Error ? error.message : String(error));
    } finally {
      setDesktopAction("");
    }
  };

  const shareDesktop = async () => {
    const api = window.pywebview?.api;
    if (!api || desktopAction) return;
    setDesktopAction("Creating public URL…");
    setDesktopError("");
    try {
      const status = await api.share_publicly();
      setDesktopHost(status);
      if (status.public_url) await navigator.clipboard.writeText(status.public_url);
    } catch (error) {
      setDesktopError(error instanceof Error ? error.message : String(error));
    } finally {
      setDesktopAction("");
    }
  };

  useEffect(() => {
    fetchAnchors()
      .then(setAnchors)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (source !== "live") return;
    const interval = window.setInterval(() => {
      setLiveTracks((previous) => pruneStaleLiveTracks(previous));
    }, 500);
    return () => window.clearInterval(interval);
  }, [source]);

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
        const nodeId = message.node_id ?? "live_tag";
        setSelectedLiveTag((current) => current || nodeId);
        setLiveTracks((previous) => appendLiveTrack(previous, message));
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
      setLiveAnchorMap(emptyLiveAnchorMap);
      setLiveSensorStatus(null);
      return;
    }

    let cancelled = false;
    const refresh = () => {
      fetchLiveUwbRanges(selectedLiveTag || undefined)
        .then((snapshot) => {
          if (!cancelled) {
            setLiveUwb(snapshot);
          }
        })
        .catch(() => undefined);
      fetchLiveAnchorMap()
        .then((snapshot) => {
          if (!cancelled) {
            if (snapshot.map_version !== liveMapVersionRef.current) {
              setLiveTracks([]);
              liveMapVersionRef.current = snapshot.map_version;
            }
            setLiveAnchorMap(snapshot);
            setAnchors(snapshot.anchors);
          }
        })
        .catch(() => undefined);
      if (selectedLiveTag) {
        fetchLiveSensorStatus(selectedLiveTag)
          .then((snapshot) => {
            if (!cancelled) setLiveSensorStatus(snapshot);
          })
          .catch(() => undefined);
      } else {
        setLiveSensorStatus(null);
      }
    };
    refresh();
    const interval = window.setInterval(refresh, 250);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [source, selectedLiveTag]);

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

  const visibleLiveAnchors = useMemo(
    () => detectedLiveAnchors(anchors, liveUwb.ranges, liveAnchorMap.links),
    [anchors, liveAnchorMap.links, liveUwb.ranges],
  );
  const activeAnchors = source === "simulation" && simulation
    ? simulation.anchors
    : source === "live" ? visibleLiveAnchors : anchors;
  const selectedTrack = source === "simulation"
    ? tracks.find((tag) => tag.node_id === selectedTag)
    : source === "live"
      ? liveTracks.find((tag) => tag.node_id === selectedLiveTag) ?? liveTracks[0]
      : undefined;
  const activeTrajectory = selectedTrack?.trajectory ?? [];
  const currentState = selectedTrack?.state ?? activeTrajectory.at(-1) ?? null;
  const displayConnected = source === "simulation" ? simulationOnline : connected;
  const usableLiveAnchorCount = useMemo(() => {
    const configuredIds = new Set(anchors.map((anchor) => anchor.anchor_id));
    return liveUwb.ranges.filter((range) => configuredIds.has(range.anchor_id)).length;
  }, [anchors, liveUwb.ranges]);
  const liveAnchorLinks = useMemo(
    () => liveAnchorMap.links.filter((link) => link.accepted && link.age_s <= 5),
    [liveAnchorMap.links],
  );
  const selectedTrackHasPosition = selectedTrack?.trajectory.some(
    (state) => state.status.active_anchor_count >= 3,
  ) ?? false;
  const livePositionResolved =
    liveAnchorMap.map_version > 0 &&
    anchors.length >= 3 &&
    selectedTrackHasPosition;
  const visualizedState = source === "live" && !livePositionResolved
    ? null
    : currentState;
  const resolvedLiveTracks = source === "live" && liveAnchorMap.map_version > 0
    ? liveTracks.filter(
      (track) => track.state !== null && track.trajectory.some(
        (state) => state.status.active_anchor_count >= 3,
      ),
    )
    : [];
  const activeTracks = source === "simulation"
    ? tracks
    : source === "live" && resolvedLiveTracks.length > 0
      ? resolvedLiveTracks
      : undefined;
  const visualizedTrajectory = source === "live" && !livePositionResolved
    ? []
    : activeTrajectory;

  return (
    <main className="app-shell">
      {desktopApp ? (
        <section className="desktop-host-bar" aria-label="Desktop host controls">
          <div>
            <strong>Mac host</strong>
            <span>{desktopAction || desktopHost?.status || "Connecting…"}</span>
          </div>
          <label htmlFor="desktop-source">Data source</label>
          <select
            id="desktop-source"
            value={desktopHost?.mode ?? "simulation"}
            disabled={!desktopHost || Boolean(desktopAction)}
            onChange={(event) => void switchDesktopMode(event.target.value as "simulation" | "udp")}
          >
            <option value="simulation">Simulation</option>
            <option value="udp">Real sensors</option>
          </select>
          <button type="button" disabled={!desktopHost?.running || Boolean(desktopAction)} onClick={() => void shareDesktop()}>
            {desktopHost?.public_url ? "Copy Public URL" : "Share Publicly"}
          </button>
          <button type="button" onClick={() => void window.pywebview?.api.open_logs()}>Logs</button>
          {desktopHost?.public_url ? (
            <span className="desktop-public-url" title={desktopHost.public_url}>{desktopHost.public_url}</span>
          ) : (
            <span className="desktop-local-url">Android: {desktopHost?.local_url ?? "starting…"}</span>
          )}
          {desktopError ? <span className="desktop-host-error">{desktopError}</span> : null}
        </section>
      ) : null}
      <header className="app-header">
        <div>
          <h1>E014 Firefighter Tracking</h1>
          <p>UWB position + waist IMU direction and lying posture</p>
        </div>
        <div className="header-actions">
          {androidViewer ? (
            <button className="server-button" type="button" onClick={() => setShowServerSetup(true)}>
              Server
            </button>
          ) : null}
          <span className={displayConnected ? "status-pill live" : "status-pill"}>{displayConnected ? source === "simulation" ? "SIMULATION" : "LIVE" : "OFFLINE"}</span>
        </div>
      </header>
      <div className="workspace">
        <div className="main-views">
          <DigitalTwinView
            anchors={activeAnchors}
            state={visualizedState}
            trajectory={visualizedTrajectory}
            liveUwb={source === "live" ? liveUwb : null}
            usableAnchorCount={usableLiveAnchorCount}
            firefighters={activeTracks}
            source={source}
            anchorLinks={source === "simulation" && simulationOnline
              ? simulation?.anchor_links
              : source === "live"
                ? liveAnchorLinks
                : undefined}
          />
          <BuildingMap
            anchors={activeAnchors}
            currentState={visualizedState}
            trajectory={visualizedTrajectory}
            liveUwb={source === "live" ? liveUwb : null}
            usableAnchorCount={usableLiveAnchorCount}
            firefighters={activeTracks}
            anchorLinks={source === "simulation" && simulationOnline
              ? simulation?.anchor_links
              : source === "live"
                ? liveAnchorLinks
                : undefined}
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
          {source === "live" && liveTracks.length > 1 ? (
            <section className="side-panel">
              <label htmlFor="inspected-live-firefighter">Inspect firefighter</label>
              <select
                id="inspected-live-firefighter"
                value={selectedTrack?.node_id ?? ""}
                onChange={(event) => setSelectedLiveTag(event.target.value)}
              >
                {liveTracks.map((tag) => (
                  <option key={tag.node_id} value={tag.node_id}>{tag.label}</option>
                ))}
              </select>
            </section>
          ) : null}
          <StatePanel
            state={source === "live" ? currentState : visualizedState}
            positionAvailable={source !== "live" || livePositionResolved}
            onAlignHeading={source === "live" && selectedTrack
              ? () => alignResponderHeading(selectedTrack.node_id, 0)
              : undefined}
          />
          <HeartRatePanel
            selectedResponderId={source === "simulation"
              ? selectedTag
              : source === "live" ? selectedTrack?.node_id : undefined}
          />
          <SensorStatus
            state={source === "live" ? currentState : visualizedState}
            connected={displayConnected}
            source={source}
            liveUwb={source === "live" ? liveUwb : null}
            anchors={activeAnchors}
            usableAnchorCount={usableLiveAnchorCount}
            liveAnchorMap={source === "live" ? liveAnchorMap : null}
            liveSensorStatus={source === "live" ? liveSensorStatus : null}
          />
          <ExperimentPlot trajectory={visualizedTrajectory} />
        </aside>
      </div>
      {showServerSetup ? (
        <div className="server-setup-backdrop" role="presentation">
          <section className="server-setup" role="dialog" aria-modal="true" aria-labelledby="server-setup-title">
            <h2 id="server-setup-title">Connect to Mac host</h2>
            <p>Paste the Local URL or Public URL shown by the E014 Mac app.</p>
            <label htmlFor="server-url">Server URL</label>
            <input
              id="server-url"
              type="url"
              placeholder="https://example.trycloudflare.com"
              value={serverUrlInput}
              onChange={(event) => {
                setServerUrlInput(event.target.value);
                setServerUrlError("");
              }}
            />
            {serverUrlError ? <p className="server-error">{serverUrlError}</p> : null}
            <div className="server-setup-actions">
              {savedServerUrl() ? (
                <button type="button" onClick={() => setShowServerSetup(false)}>Cancel</button>
              ) : null}
              <button className="primary" type="button" onClick={applyServerUrl}>Connect</button>
            </div>
            {savedServerUrl() ? <small>Current: {backendHttpUrl()}</small> : null}
          </section>
        </div>
      ) : null}
    </main>
  );
}
