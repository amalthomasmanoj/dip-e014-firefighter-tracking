import { Anchor } from "../types/state";

export type BuildingFootprint = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  centerX: number;
  centerY: number;
  width: number;
  depth: number;
};

const BUILDING_MAP_MARGIN_M = 0.6;

export function buildingFootprintFromAnchors(anchors: Anchor[]): BuildingFootprint | null {
  if (anchors.length === 0) {
    return null;
  }
  const minX = Math.min(...anchors.map((anchor) => anchor.x_m)) - BUILDING_MAP_MARGIN_M;
  const maxX = Math.max(...anchors.map((anchor) => anchor.x_m)) + BUILDING_MAP_MARGIN_M;
  const minY = Math.min(...anchors.map((anchor) => anchor.y_m)) - BUILDING_MAP_MARGIN_M;
  const maxY = Math.max(...anchors.map((anchor) => anchor.y_m)) + BUILDING_MAP_MARGIN_M;
  return {
    minX,
    maxX,
    minY,
    maxY,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
    width: maxX - minX,
    depth: maxY - minY,
  };
}
