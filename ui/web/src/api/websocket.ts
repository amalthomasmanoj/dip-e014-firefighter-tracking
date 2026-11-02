import { StateMessage } from "../types/state";
import { backendWebSocketUrl } from "./server";

export function connectStateStream(
  onMessage: (message: StateMessage) => void,
  onConnectionChange: (connected: boolean) => void,
): WebSocket {
  const url = backendWebSocketUrl();
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

