export type WorldPoint = {
  x: number;
  y: number;
};

export type MapTransform = {
  scale: number;
  rotationRad: number;
  translateX: number;
  translateY: number;
};

function assertFiniteTransform(transform: MapTransform): void {
  for (const value of [
    transform.scale,
    transform.rotationRad,
    transform.translateX,
    transform.translateY,
  ]) {
    if (!Number.isFinite(value)) {
      throw new Error("map transform contains a non-finite value");
    }
  }
  if (transform.scale === 0) {
    throw new Error("map transform scale must be non-zero");
  }
}

export function worldToMap(position: WorldPoint, transform: MapTransform): WorldPoint {
  assertFiniteTransform(transform);
  if (!Number.isFinite(position.x) || !Number.isFinite(position.y)) {
    throw new Error("world position contains a non-finite value");
  }

  const c = Math.cos(transform.rotationRad);
  const s = Math.sin(transform.rotationRad);
  return {
    x: transform.scale * (c * position.x - s * position.y) + transform.translateX,
    y: transform.scale * (s * position.x + c * position.y) + transform.translateY,
  };
}

export function mapToWorld(position: WorldPoint, transform: MapTransform): WorldPoint {
  assertFiniteTransform(transform);
  if (!Number.isFinite(position.x) || !Number.isFinite(position.y)) {
    throw new Error("map position contains a non-finite value");
  }

  const x = (position.x - transform.translateX) / transform.scale;
  const y = (position.y - transform.translateY) / transform.scale;
  const c = Math.cos(-transform.rotationRad);
  const s = Math.sin(-transform.rotationRad);
  return {
    x: c * x - s * y,
    y: s * x + c * y,
  };
}

