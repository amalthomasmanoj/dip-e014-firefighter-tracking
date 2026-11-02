import { Anchor } from "../types/state";
import { backendHttpUrl } from "./server";

export async function fetchAnchors(): Promise<Anchor[]> {
  const baseUrl = backendHttpUrl();
  const response = await fetch(`${baseUrl}/anchors`);
  if (!response.ok) {
    throw new Error(`failed to load anchors: ${response.status}`);
  }
  return response.json() as Promise<Anchor[]>;
}
