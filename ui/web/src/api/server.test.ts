import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  backendHttpUrl,
  backendWebSocketUrl,
  saveServerUrl,
} from "./server";

const values = new Map<string, string>();

beforeEach(() => {
  values.clear();
  vi.stubGlobal("window", {
    location: { protocol: "https:", origin: "https://dashboard.test", port: "" },
    localStorage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      clear: () => values.clear(),
    },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("runtime server address", () => {
  it("uses the page origin for a packaged or publicly hosted UI", () => {
    expect(backendHttpUrl()).toBe("https://dashboard.test");
  });

  it("persists an Android viewer server and derives secure WebSockets", () => {
    expect(saveServerUrl("https://demo.trycloudflare.com/"))
      .toBe("https://demo.trycloudflare.com");
    expect(backendHttpUrl()).toBe("https://demo.trycloudflare.com");
    expect(backendWebSocketUrl()).toBe("wss://demo.trycloudflare.com/ws/state");
  });

  it("keeps the Vite development server connected to the backend port", () => {
    vi.stubGlobal("window", {
      ...window,
      location: { protocol: "http:", origin: "http://localhost:5173", port: "5173" },
    });
    expect(backendHttpUrl()).toBe("http://localhost:8000");
    expect(backendWebSocketUrl()).toBe("ws://localhost:8000/ws/state");
  });

  it("rejects non-HTTP server addresses", () => {
    expect(() => saveServerUrl("file:///tmp/index.html")).toThrow("http:// or https://");
  });
});
