import { AnchorLink, FirefighterTrack } from "../api/simulation";
import { useEffect, useRef, type MutableRefObject } from "react";
import * as THREE from "three";
import {
  Anchor,
  EstimatedState,
  LiveUwbSnapshot,
  UwbRangeReading,
} from "../types/state";

type Props = {
  anchors: Anchor[];
  state: EstimatedState | null;
  trajectory: EstimatedState[];
  liveUwb: LiveUwbSnapshot | null;
  usableAnchorCount: number;
  firefighters?: FirefighterTrack[];
  anchorLinks?: AnchorLink[];
};

type AvatarParts = {
  root: THREE.Group;
  torso: THREE.Mesh;
  head: THREE.Mesh;
  leftLeg: THREE.Mesh;
  rightLeg: THREE.Mesh;
  leftArm: THREE.Mesh;
  rightArm: THREE.Mesh;
  beacon: THREE.Mesh;
};

function headingFromQuaternion(q: EstimatedState["orientation_xyzw"]): number {
  return Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
}

function createCylinder(
  radius: number,
  height: number,
  material: THREE.Material,
): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, 18), material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function createAvatar(color = 0xd83a2e): AvatarParts {
  const root = new THREE.Group();
  const coatMaterial = new THREE.MeshStandardMaterial({ color, roughness: 0.58 });
  const stripeMaterial = new THREE.MeshStandardMaterial({ color: 0xf7c948, roughness: 0.45 });
  const helmetMaterial = new THREE.MeshStandardMaterial({ color: 0xffd447, roughness: 0.38 });
  const limbMaterial = new THREE.MeshStandardMaterial({ color: 0x263241, roughness: 0.65 });
  const beaconMaterial = new THREE.MeshStandardMaterial({
    color: 0x28d17c,
    emissive: 0x116b3f,
    emissiveIntensity: 0.6,
  });

  const torso = createCylinder(0.18, 0.74, coatMaterial);
  const chestStripe = createCylinder(0.185, 0.055, stripeMaterial);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.16, 24, 18), helmetMaterial);
  const leftLeg = createCylinder(0.055, 0.72, limbMaterial);
  const rightLeg = createCylinder(0.055, 0.72, limbMaterial);
  const leftArm = createCylinder(0.045, 0.62, limbMaterial);
  const rightArm = createCylinder(0.045, 0.62, limbMaterial);
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 12), beaconMaterial);

  root.add(torso, chestStripe, head, leftLeg, rightLeg, leftArm, rightArm, beacon);
  return { root, torso, head, leftLeg, rightLeg, leftArm, rightArm, beacon };
}

function createTextSprite(text: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 320;
  canvas.height = 72;
  const context = canvas.getContext("2d");
  if (context) {
    context.fillStyle = "rgba(255, 255, 255, 0.9)";
    context.roundRect(2, 2, 316, 68, 14);
    context.fill();
    context.fillStyle = "#3974a8";
    context.font = `700 ${text.length > 18 ? 20 : 30}px system-ui`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, 160, 37);
  }
  const texture = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true }),
  );
  sprite.scale.set(1.25, 0.28, 1);
  return sprite;
}

function clearVisualGroup(group: THREE.Object3D): void {
  for (const child of [...group.children]) {
    child.traverse((object) => {
      const visual = object as THREE.Mesh;
      visual.geometry?.dispose();
      const materials = Array.isArray(visual.material) ? visual.material : [visual.material];
      materials.filter(Boolean).forEach((material) => {
        const spriteMaterial = material as THREE.SpriteMaterial;
        spriteMaterial.map?.dispose();
        material.dispose();
      });
    });
    group.remove(child);
  }
}

function updateAvatar(parts: AvatarParts, state: EstimatedState | null, elapsedS: number): void {
  const root = parts.root;
  if (!state) {
    root.visible = false;
    return;
  }

  root.visible = true;

  const lying = state.activity.posture === "lying_down";
  const headingRad = -headingFromQuaternion(state.orientation_xyzw);

  // A prone responder keeps their heading but the body axis tips onto the
  // floor, so compose the tip after the heading instead of overwriting it.
  root.position.set(state.position_m.x, lying ? 0.22 : 0, -state.position_m.y);
  root.quaternion.setFromEuler(new THREE.Euler(0, headingRad, 0));
  if (lying) {
    root.quaternion.multiply(
      new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.PI / 2),
    );
  }

  const walking = state.activity.motion === "walking" && !lying;
  const crouching = state.activity.posture === "crouching";
  const gait = walking ? Math.sin(elapsedS * 8.5) : 0;
  const crouchDrop = crouching ? 0.34 : 0;
  const legHeight = crouching ? 0.48 : 0.72;
  const torsoHeight = crouching ? 0.58 : 0.74;

  parts.torso.scale.y = torsoHeight / 0.74;
  parts.torso.position.set(0, 0.98 - crouchDrop, 0);
  parts.torso.rotation.z = crouching ? -0.18 : 0;

  parts.head.position.set(0.02, 1.47 - crouchDrop, 0);
  parts.beacon.position.set(0.02, 1.68 - crouchDrop, 0);

  parts.leftLeg.scale.y = legHeight / 0.72;
  parts.rightLeg.scale.y = legHeight / 0.72;
  parts.leftLeg.position.set(-0.095, legHeight / 2, 0);
  parts.rightLeg.position.set(0.095, legHeight / 2, 0);
  parts.leftLeg.rotation.x = gait * 0.38 + (crouching ? 0.42 : 0);
  parts.rightLeg.rotation.x = -gait * 0.38 + (crouching ? 0.42 : 0);
  parts.leftLeg.rotation.z = crouching ? -0.18 : 0;
  parts.rightLeg.rotation.z = crouching ? 0.18 : 0;

  parts.leftArm.position.set(-0.27, 0.98 - crouchDrop, 0);
  parts.rightArm.position.set(0.27, 0.98 - crouchDrop, 0);
  parts.leftArm.rotation.x = -gait * 0.32;
  parts.rightArm.rotation.x = gait * 0.32;
  parts.leftArm.rotation.z = crouching ? 0.34 : 0.18;
  parts.rightArm.rotation.z = crouching ? -0.34 : -0.18;
}

function updateTrajectory(line: THREE.Line, trajectory: EstimatedState[]): void {
  const points = trajectory.map((state) => new THREE.Vector3(state.position_m.x, 0.035, -state.position_m.y));
  line.geometry.dispose();
  line.geometry = new THREE.BufferGeometry().setFromPoints(points);
}

function runCanvasFallback(
  container: HTMLDivElement,
  stateRef: MutableRefObject<EstimatedState | null>,
  trajectoryRef: MutableRefObject<EstimatedState[]>,
  anchorsRef: MutableRefObject<Anchor[]>,
  rangesRef: MutableRefObject<UwbRangeReading[]>,
  firefightersRef: MutableRefObject<FirefighterTrack[] | undefined>,
  linksRef: MutableRefObject<AnchorLink[]>,
): () => void {
  const canvas = document.createElement("canvas");
  const canvasContext = canvas.getContext("2d");
  if (!canvasContext) {
    return () => undefined;
  }
  const context: CanvasRenderingContext2D = canvasContext;

  canvas.className = "twin-fallback-canvas";
  container.appendChild(canvas);

  function resize() {
    const pixelRatio = Math.min(window.devicePixelRatio, 2);
    canvas.width = Math.max(1, Math.floor(container.clientWidth * pixelRatio));
    canvas.height = Math.max(1, Math.floor(container.clientHeight * pixelRatio));
    canvas.style.width = `${container.clientWidth}px`;
    canvas.style.height = `${container.clientHeight}px`;
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  }

  function project(xM: number, yM: number, zM = 0) {
    return {
      x: container.clientWidth * 0.18 + xM * 66 + yM * 34,
      y: container.clientHeight * 0.76 - xM * 18 - yM * 42 - zM * 70,
    };
  }

  function drawAvatar(state: EstimatedState, elapsedS: number, color = "#d83a2e") {
    const point = project(state.position_m.x, state.position_m.y);
    const lying = state.activity.posture === "lying_down";
    const walking = state.activity.motion === "walking" && !lying;
    const crouching = state.activity.posture === "crouching";
    const gait = walking ? Math.sin(elapsedS * 8.5) : 0;
    const bodyHeight = crouching ? 42 : 68;
    const legHeight = crouching ? 22 : 38;

    context.save();
    context.translate(point.x, point.y);
    context.rotate(-headingFromQuaternion(state.orientation_xyzw) * 0.35);
    if (lying) {
      // Tip the whole figure onto its side and drop it to floor level.
      context.rotate(Math.PI / 2);
      context.translate(0, 34);
    }
    context.lineCap = "round";
    context.lineJoin = "round";

    context.strokeStyle = "#263241";
    context.lineWidth = 7;
    context.beginPath();
    context.moveTo(-8, 0);
    context.lineTo(-14 - gait * 5, legHeight);
    context.moveTo(8, 0);
    context.lineTo(14 + gait * 5, legHeight);
    context.stroke();

    context.strokeStyle = "#243344";
    context.lineWidth = 6;
    context.beginPath();
    context.moveTo(-18, -bodyHeight + 18);
    context.lineTo(-26 + gait * 4, -bodyHeight + 45);
    context.moveTo(18, -bodyHeight + 18);
    context.lineTo(26 - gait * 4, -bodyHeight + 45);
    context.stroke();

    context.fillStyle = color;
    context.fillRect(-18, -bodyHeight, 36, bodyHeight);
    context.fillStyle = "#f7c948";
    context.fillRect(-19, -bodyHeight + 20, 38, 6);
    context.fillStyle = "#ffd447";
    context.beginPath();
    context.arc(0, -bodyHeight - 13, 13, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#28d17c";
    context.beginPath();
    context.arc(0, -bodyHeight - 31, 4, 0, Math.PI * 2);
    context.fill();
    context.restore();
  }

  function draw(elapsedS: number) {
    const width = container.clientWidth;
    const height = container.clientHeight;
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#f7f9fb";
    context.fillRect(0, 0, width, height);

    context.strokeStyle = "#d8dee6";
    context.lineWidth = 1;
    for (let x = 0; x <= 8; x += 1) {
      const start = project(x, 0);
      const end = project(x, 6);
      context.beginPath();
      context.moveTo(start.x, start.y);
      context.lineTo(end.x, end.y);
      context.stroke();
    }
    for (let y = 0; y <= 6; y += 1) {
      const start = project(0, y);
      const end = project(8, y);
      context.beginPath();
      context.moveTo(start.x, start.y);
      context.lineTo(end.x, end.y);
      context.stroke();
    }

    const tracks = firefightersRef.current;
    const trails = tracks?.map((tag, index) => ({ states: tag.trajectory, color: index === 0 ? "#f08c2e" : "#008f92" }))
      ?? [{ states: trajectoryRef.current, color: "#f08c2e" }];
    trails.forEach(({ states: trajectory, color }) => {
    if (trajectory.length > 1) {
      context.strokeStyle = color;
      context.lineWidth = 4;
      context.beginPath();
      trajectory.forEach((state, index) => {
        const point = project(state.position_m.x, state.position_m.y, 0.02);
        if (index === 0) {
          context.moveTo(point.x, point.y);
        } else {
          context.lineTo(point.x, point.y);
        }
      });
      context.stroke();
    }

    });
    context.save();
    context.strokeStyle = "#4a9a83";
    context.setLineDash([6, 6]);
    context.lineDashOffset = -elapsedS * 15;
    linksRef.current.forEach((link) => {
      const a = anchorsRef.current.find((anchor) => anchor.anchor_id === link.initiator_id);
      const b = anchorsRef.current.find((anchor) => anchor.anchor_id === link.responder_id);
      if (!a || !b) return;
      const start = project(a.x_m, a.y_m, 0.7);
      const end = project(b.x_m, b.y_m, 0.7);
      context.beginPath();
      context.moveTo(start.x, start.y);
      context.lineTo(end.x, end.y);
      context.stroke();
      context.fillStyle = "#3974a8";
      context.fillText(`${link.raw_range_m.toFixed(2)} m`, (start.x + end.x) / 2, (start.y + end.y) / 2 - 6);
    });
    context.restore();
    anchorsRef.current.forEach((anchor) => {
      const base = project(anchor.x_m, anchor.y_m);
      const top = project(anchor.x_m, anchor.y_m, 0.7);
      context.strokeStyle = "#1f6feb";
      context.lineWidth = 5;
      context.beginPath();
      context.moveTo(base.x, base.y);
      context.lineTo(top.x, top.y);
      context.stroke();
      context.fillStyle = "#1f6feb";
      context.beginPath();
      context.arc(top.x, top.y, 7, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = "#1f6feb";
      context.font = "700 12px system-ui";
      context.fillText(anchor.anchor_id, top.x + 10, top.y - 8);
    });

    const state = stateRef.current;
    context.save();
    context.strokeStyle = "#72a7d8";
    context.fillStyle = "#3974a8";
    context.font = "700 12px system-ui";
    context.setLineDash([3, 7]);
    rangesRef.current.forEach((range) => {
      const anchor = anchorsRef.current.find((item) => item.anchor_id === range.anchor_id);
      if (!anchor) {
        return;
      }
      const anchorPoint = project(anchor.x_m, anchor.y_m, 0.7);
      if (state) {
        const tagPoint = project(state.position_m.x, state.position_m.y, 0.85);
        context.beginPath();
        context.moveTo(tagPoint.x, tagPoint.y);
        context.lineTo(anchorPoint.x, anchorPoint.y);
        context.stroke();
        context.fillText(
          `${range.range_m.toFixed(2)} m`,
          (tagPoint.x + anchorPoint.x) / 2 + 6,
          (tagPoint.y + anchorPoint.y) / 2 - 6,
        );
      } else {
        context.beginPath();
        context.arc(anchorPoint.x, anchorPoint.y, Math.max(14, range.range_m * 28), 0, Math.PI * 2);
        context.stroke();
        context.fillText(`${range.range_m.toFixed(2)} m`, anchorPoint.x + 12, anchorPoint.y + 22);
      }
    });
    context.restore();

    if (tracks) {
      tracks.forEach((tag, index) => {
        if (!tag.state) return;
        drawAvatar(tag.state, elapsedS, index === 0 ? "#d83a2e" : "#008f92");
        const point = project(tag.state.position_m.x, tag.state.position_m.y, 1.8);
        context.fillStyle = "#25313d";
        context.fillText(tag.label, point.x - 25, point.y);
      });
    } else if (state) {
      drawAvatar(state, elapsedS);
    }
  }

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();

  let animationFrame = 0;
  const startedAt = performance.now();
  function animate(now: number) {
    draw((now - startedAt) / 1000);
    animationFrame = window.requestAnimationFrame(animate);
  }
  animate(startedAt);

  return () => {
    window.cancelAnimationFrame(animationFrame);
    resizeObserver.disconnect();
    container.removeChild(canvas);
  };
}

export function DigitalTwinView({
  anchors,
  state,
  trajectory,
  liveUwb,
  usableAnchorCount,
  firefighters,
  anchorLinks,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef(state);
  const firefightersRef = useRef(firefighters);
  const linksRef = useRef(anchorLinks ?? []);
  const trajectoryRef = useRef(trajectory);
  const anchorsRef = useRef(anchors);
  const rangesRef = useRef(liveUwb?.ranges ?? []);

  useEffect(() => {
    stateRef.current = state;
    firefightersRef.current = firefighters;
    linksRef.current = anchorLinks ?? [];
    trajectoryRef.current = trajectory;
    anchorsRef.current = anchors;
    rangesRef.current = liveUwb?.ranges ?? [];
  }, [anchors, liveUwb?.ranges, state, trajectory, firefighters, anchorLinks]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const activeContainer = container;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf7f9fb);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    const cameraTarget = new THREE.Vector3(4, 0.5, -3);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      return runCanvasFallback(
        activeContainer,
        stateRef,
        trajectoryRef,
        anchorsRef,
        rangesRef,
        firefightersRef,
        linksRef,
      );
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    activeContainer.appendChild(renderer.domElement);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x8fa1b2, 1.6);
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
    keyLight.position.set(4, 7, 2);
    keyLight.castShadow = true;
    scene.add(hemiLight, keyLight);

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(9, 7),
      new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.8 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(4, 0, -3);
    floor.receiveShadow = true;
    scene.add(floor);

    const grid = new THREE.GridHelper(9, 18, 0x9aa9b8, 0xd8dee6);
    grid.position.set(4, 0.01, -3);
    scene.add(grid);

    const anchorGroup = new THREE.Group();
    scene.add(anchorGroup);

    const rangeGroup = new THREE.Group();
    scene.add(rangeGroup);

    const trajectoryLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0xf08c2e, linewidth: 3 }),
    );
    scene.add(trajectoryLine);

    const avatar = createAvatar();
    scene.add(avatar.root);
    const firefighterVisuals = new Map<string, { avatar: AvatarParts; trail: THREE.Line; label: THREE.Sprite }>();
    const peerGroup = new THREE.Group();
    scene.add(peerGroup);
    function syncFirefighters(elapsedS: number) {
      const tracks = firefightersRef.current;
      firefighterVisuals.forEach((visual, nodeId) => {
        const present = tracks?.some((tag) => tag.node_id === nodeId) ?? false;
        visual.avatar.root.visible = present;
        visual.trail.visible = present;
        visual.label.visible = present;
      });
      if (!tracks) return;
      tracks.forEach((tag, index) => {
        let visual = firefighterVisuals.get(tag.node_id);
        if (!visual) {
          visual = {
            avatar: createAvatar(index === 0 ? 0xd83a2e : 0x008f92),
            trail: new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: index === 0 ? 0xf08c2e : 0x008f92 })),
            label: createTextSprite(tag.label),
          };
          visual.label.scale.set(1.8, 0.4, 1);
          scene.add(visual.avatar.root, visual.trail, visual.label);
          firefighterVisuals.set(tag.node_id, visual);
        }
        updateAvatar(visual.avatar, tag.state, elapsedS);
        if (visual.trail.userData.trajectory !== tag.trajectory) {
          updateTrajectory(visual.trail, tag.trajectory);
          visual.trail.userData.trajectory = tag.trajectory;
        }
        visual.label.visible = tag.state !== null;
        if (tag.state) visual.label.position.set(tag.state.position_m.x, 2, -tag.state.position_m.y);
      });
    }
    function syncPeerLinks() {
      clearVisualGroup(peerGroup);
      linksRef.current.forEach((link) => {
        const a = anchorsRef.current.find((item) => item.anchor_id === link.initiator_id);
        const b = anchorsRef.current.find((item) => item.anchor_id === link.responder_id);
        if (!a || !b) return;
        const start = new THREE.Vector3(a.x_m, 0.76, -a.y_m);
        const end = new THREE.Vector3(b.x_m, 0.76, -b.y_m);
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([start, end]),
          new THREE.LineDashedMaterial({ color: 0x4a9a83, dashSize: 0.12, gapSize: 0.12 }));
        line.computeLineDistances();
        const label = createTextSprite(`${link.raw_range_m.toFixed(2)} m`);
        label.position.copy(start).add(end).multiplyScalar(0.5);
        label.position.y += 0.15;
        const pulse = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 6), new THREE.MeshBasicMaterial({ color: 0x39b58e }));
        pulse.userData.start = start;
        pulse.userData.end = end;
        peerGroup.add(line, label, pulse);
      });
    }

    function resize() {
      const { clientWidth, clientHeight } = activeContainer;
      renderer.setSize(clientWidth, clientHeight, false);
      camera.aspect = clientWidth / Math.max(clientHeight, 1);
      const verticalFov = THREE.MathUtils.degToRad(camera.fov);
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
      const distance = 6 / Math.sin(Math.min(verticalFov, horizontalFov) / 2);
      camera.position.copy(cameraTarget).add(
        new THREE.Vector3(0.45, 0.65, 1).normalize().multiplyScalar(distance),
      );
      camera.lookAt(cameraTarget);
      camera.updateProjectionMatrix();
    }

    function syncAnchors() {
      clearVisualGroup(anchorGroup);
      const postMaterial = new THREE.MeshStandardMaterial({ color: 0x1f6feb, roughness: 0.45 });
      const labelMaterial = new THREE.MeshStandardMaterial({ color: 0x1f6feb, roughness: 0.45 });
      anchorsRef.current.forEach((anchor) => {
        const post = createCylinder(0.06, 0.7, postMaterial);
        post.position.set(anchor.x_m, 0.35, -anchor.y_m);
        const top = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 12), labelMaterial);
        top.position.set(anchor.x_m, 0.76, -anchor.y_m);
        const label = createTextSprite(anchor.anchor_id);
        label.position.set(anchor.x_m + 0.34, 1.03, -anchor.y_m);
        label.scale.set(0.9, 0.23, 1);
        anchorGroup.add(post, top, label);
      });
    }

    function syncRangeLinks() {
      clearVisualGroup(rangeGroup);
      const state = stateRef.current;
      const anchorsById = new Map(
        anchorsRef.current.map((anchor) => [anchor.anchor_id, anchor]),
      );
      rangesRef.current.forEach((range) => {
        const anchor = anchorsById.get(range.anchor_id);
        if (!anchor) {
          return;
        }
        const material = new THREE.LineDashedMaterial({
          color: 0x72a7d8,
          dashSize: 0.08,
          gapSize: 0.12,
          opacity: 0.72,
          transparent: true,
        });

        if (state) {
          const tagPoint = new THREE.Vector3(
            state.position_m.x,
            0.88,
            -state.position_m.y,
          );
          const anchorPoint = new THREE.Vector3(anchor.x_m, 0.76, -anchor.y_m);
          const line = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([tagPoint, anchorPoint]),
            material,
          );
          line.computeLineDistances();
          const label = createTextSprite(`${range.range_m.toFixed(2)} m`);
          label.position.copy(tagPoint).add(anchorPoint).multiplyScalar(0.5);
          label.position.y += 0.18;
          rangeGroup.add(line, label);
          return;
        }

        const circlePoints = Array.from({ length: 97 }, (_value, index) => {
          const angle = (index / 96) * Math.PI * 2;
          return new THREE.Vector3(
            anchor.x_m + Math.cos(angle) * range.range_m,
            0.035,
            -anchor.y_m - Math.sin(angle) * range.range_m,
          );
        });
        const circle = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(circlePoints),
          material,
        );
        circle.computeLineDistances();
        const label = createTextSprite(`${range.range_m.toFixed(2)} m`);
        label.position.set(anchor.x_m + 0.45, 1.18, -anchor.y_m);
        rangeGroup.add(circle, label);
      });
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(activeContainer);
    resize();
    syncAnchors();
    syncRangeLinks();

    let previousVisualSignature = "";
    let animationFrame = 0;
    const startedAtMs = performance.now();

    function animate() {
      const elapsedS = (performance.now() - startedAtMs) / 1000;
      const visualSignature = JSON.stringify({
        anchors: anchorsRef.current,
        links: linksRef.current.map((link) => [link.initiator_id, link.responder_id, link.raw_range_m]),
        ranges: rangesRef.current.map((range) => [range.anchor_id, range.range_m]),
        state: stateRef.current
          ? [stateRef.current.position_m.x, stateRef.current.position_m.y]
          : null,
      });
      if (previousVisualSignature !== visualSignature) {
        syncAnchors();
        syncRangeLinks();
        syncPeerLinks();
        previousVisualSignature = visualSignature;
      }
      updateAvatar(avatar, firefightersRef.current ? null : stateRef.current, elapsedS);
      trajectoryLine.visible = !firefightersRef.current;
      if (trajectoryLine.userData.trajectory !== trajectoryRef.current) {
        updateTrajectory(trajectoryLine, trajectoryRef.current);
        trajectoryLine.userData.trajectory = trajectoryRef.current;
      }
      syncFirefighters(elapsedS);
      peerGroup.children.forEach((child) => {
        if (child.userData.start) {
          const phase = (elapsedS % 2) / 2;
          child.position.lerpVectors(child.userData.start, child.userData.end, phase < 0.5 ? phase * 2 : 2 - phase * 2);
        }
      });
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    }

    animate();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      renderer.dispose();
      clearVisualGroup(scene);
      activeContainer.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <section className="twin-panel">
      <div className="twin-header">
        <h2>Digital Twin</h2>
        <span className="twin-activity">
          {firefighters ? `${firefighters.length} firefighters · simulation` : state
            ? state.activity.posture === "lying_down"
              ? `LYING DOWN · ${state.activity.motion}`
              : `${state.activity.posture} ${state.activity.motion}`
            : liveUwb?.tag_present
              ? `tag detected · ${usableAnchorCount}/3 mapped anchors`
              : "waiting for tag"}
        </span>
      </div>
      {liveUwb?.ranges.length ? (
        <div className="twin-range-strip">
          {liveUwb.ranges.map((range) => (
            <span key={range.anchor_id}>
              {range.anchor_id} <strong>{range.range_m.toFixed(2)} m</strong>
            </span>
          ))}
        </div>
      ) : null}
      <div className="twin-canvas" ref={containerRef} />
    </section>
  );
}
