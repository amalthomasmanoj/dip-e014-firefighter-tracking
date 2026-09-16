import { useEffect, useRef, type MutableRefObject } from "react";
import * as THREE from "three";
import { Anchor, EstimatedState } from "../types/state";

type Props = {
  anchors: Anchor[];
  state: EstimatedState | null;
  trajectory: EstimatedState[];
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

function createAvatar(): AvatarParts {
  const root = new THREE.Group();
  const coatMaterial = new THREE.MeshStandardMaterial({ color: 0xd83a2e, roughness: 0.58 });
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

function updateAvatar(parts: AvatarParts, state: EstimatedState | null, elapsedS: number): void {
  const root = parts.root;
  if (!state) {
    root.visible = false;
    return;
  }

  root.visible = true;
  root.position.set(state.position_m.x, 0, -state.position_m.y);
  root.rotation.y = -headingFromQuaternion(state.orientation_xyzw);

  const walking = state.activity.motion === "walking";
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

  function drawAvatar(state: EstimatedState, elapsedS: number) {
    const point = project(state.position_m.x, state.position_m.y);
    const walking = state.activity.motion === "walking";
    const crouching = state.activity.posture === "crouching";
    const gait = walking ? Math.sin(elapsedS * 8.5) : 0;
    const bodyHeight = crouching ? 42 : 68;
    const legHeight = crouching ? 22 : 38;

    context.save();
    context.translate(point.x, point.y);
    context.rotate(-headingFromQuaternion(state.orientation_xyzw) * 0.35);
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

    context.fillStyle = "#d83a2e";
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

    const trajectory = trajectoryRef.current;
    if (trajectory.length > 1) {
      context.strokeStyle = "#f08c2e";
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
    });

    const state = stateRef.current;
    if (state) {
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

export function DigitalTwinView({ anchors, state, trajectory }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef(state);
  const trajectoryRef = useRef(trajectory);
  const anchorsRef = useRef(anchors);

  useEffect(() => {
    stateRef.current = state;
    trajectoryRef.current = trajectory;
    anchorsRef.current = anchors;
  }, [anchors, state, trajectory]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const activeContainer = container;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf7f9fb);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(5.8, 5.0, 7.0);
    camera.lookAt(3.2, 0.2, -2.2);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      return runCanvasFallback(activeContainer, stateRef, trajectoryRef, anchorsRef);
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

    const trajectoryLine = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0xf08c2e, linewidth: 3 }),
    );
    scene.add(trajectoryLine);

    const avatar = createAvatar();
    scene.add(avatar.root);

    function resize() {
      const { clientWidth, clientHeight } = activeContainer;
      renderer.setSize(clientWidth, clientHeight, false);
      camera.aspect = clientWidth / Math.max(clientHeight, 1);
      camera.updateProjectionMatrix();
    }

    function syncAnchors() {
      anchorGroup.clear();
      const postMaterial = new THREE.MeshStandardMaterial({ color: 0x1f6feb, roughness: 0.45 });
      const labelMaterial = new THREE.MeshStandardMaterial({ color: 0x1f6feb, roughness: 0.45 });
      anchorsRef.current.forEach((anchor) => {
        const post = createCylinder(0.06, 0.7, postMaterial);
        post.position.set(anchor.x_m, 0.35, -anchor.y_m);
        const top = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 12), labelMaterial);
        top.position.set(anchor.x_m, 0.76, -anchor.y_m);
        anchorGroup.add(post, top);
      });
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(activeContainer);
    resize();
    syncAnchors();

    let previousAnchorCount = -1;
    let animationFrame = 0;
    const clock = new THREE.Clock();

    function animate() {
      const elapsedS = clock.getElapsedTime();
      if (previousAnchorCount !== anchorsRef.current.length) {
        syncAnchors();
        previousAnchorCount = anchorsRef.current.length;
      }
      updateAvatar(avatar, stateRef.current, elapsedS);
      updateTrajectory(trajectoryLine, trajectoryRef.current);
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    }

    animate();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      renderer.dispose();
      trajectoryLine.geometry.dispose();
      activeContainer.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <section className="twin-panel">
      <div className="twin-header">
        <h2>Digital Twin</h2>
        <span className="twin-activity">
          {state ? `${state.activity.posture} ${state.activity.motion}` : "waiting for state"}
        </span>
      </div>
      <div className="twin-canvas" ref={containerRef} />
    </section>
  );
}
