const SERVER_URL_STORAGE_KEY = "e014.serverUrl";

function withoutTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function environmentServerUrl(): string | undefined {
  const configured = import.meta.env.VITE_BACKEND_HTTP_URL?.trim();
  return configured ? withoutTrailingSlash(configured) : undefined;
}

export function savedServerUrl(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(SERVER_URL_STORAGE_KEY)?.trim();
    return value ? withoutTrailingSlash(value) : null;
  } catch {
    return null;
  }
}

export function backendHttpUrl(): string {
  const configured = savedServerUrl() ?? environmentServerUrl();
  if (configured) return configured;
  if (
    typeof window !== "undefined" &&
    window.location.port === "5173"
  ) {
    return "http://localhost:8000";
  }
  if (
    typeof window !== "undefined" &&
    (window.location.protocol === "http:" || window.location.protocol === "https:")
  ) {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

export function backendWebSocketUrl(): string {
  const configured = import.meta.env.VITE_STATE_WS_URL?.trim();
  if (configured && !savedServerUrl()) return configured;
  const url = new URL(backendHttpUrl());
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/state";
  url.search = "";
  url.hash = "";
  return url.toString();
}

export function saveServerUrl(value: string): string {
  const candidate = value.trim();
  if (!candidate) throw new Error("Enter the Mac app or public server URL.");
  const parsed = new URL(candidate);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("The server URL must start with http:// or https://.");
  }
  parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  parsed.search = "";
  parsed.hash = "";
  const normalized = withoutTrailingSlash(parsed.toString());
  if (typeof window === "undefined") {
    throw new Error("Server URLs can only be saved in the app.");
  }
  window.localStorage.setItem(SERVER_URL_STORAGE_KEY, normalized);
  return normalized;
}

export function isAndroidViewer(): boolean {
  return import.meta.env.VITE_ANDROID_APP === "true";
}
