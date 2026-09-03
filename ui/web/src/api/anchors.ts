import { Anchor } from "../types/state";

export async function fetchAnchors(): Promise<Anchor[]> {
  const baseUrl = import.meta.env.VITE_BACKEND_HTTP_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}/anchors`);
  if (!response.ok) {
    throw new Error(`failed to load anchors: ${response.status}`);
  }
  return response.json() as Promise<Anchor[]>;
}
