import { StateMessage } from "../types/state";

export function connectStateStream(
  onMessage: (message: StateMessage) => void,
  onConnectionChange: (connected: boolean) => void,
): WebSocket {
  const url = import.meta.env.VITE_STATE_WS_URL ?? "ws://localhost:8000/ws/state";
  const socket = new WebSocket(url);

  socket.addEventListener("open", () => onConnectionChange(true));
  socket.addEventListener("close", () => onConnectionChange(false));
  socket.addEventListener("error", () => onConnectionChange(false));
  socket.addEventListener("message", (event) => {
    const parsed = JSON.parse(event.data) as StateMessage;
    if (parsed.type === "estimated_state") {
      onMessage(parsed);
    }
  });

  return socket;
}

