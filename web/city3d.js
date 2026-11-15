// Vexcel 3D Cities around one place: textured city mesh tiles, orbitable. Tiles come through this
// server (/api/vexcel3d/...), which holds the key; nothing here talks to Vexcel directly.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { KTX2Loader } from "three/addons/loaders/KTX2Loader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const A = 6378137.0;
const F = 1 / 298.257223563;
const E2 = F * (2 - F);
const rad = (d) => (d * Math.PI) / 180;

function ecef(lat, lon, h = 0) {
  const p = rad(lat), l = rad(lon);
  const n = A / Math.sqrt(1 - E2 * Math.sin(p) ** 2);
  return [(n + h) * Math.cos(p) * Math.cos(l), (n + h) * Math.cos(p) * Math.sin(l), (n * (1 - E2) + h) * Math.sin(p)];
}

// Earth-centred coordinates -> three.js local frame at the place: x east, y up, z south.
function localFrame(lat, lon) {
  const p = rad(lat), l = rad(lon);
  const east = [-Math.sin(l), Math.cos(l), 0];
  const north = [-Math.sin(p) * Math.cos(l), -Math.sin(p) * Math.sin(l), Math.cos(p)];
  const up = [Math.cos(p) * Math.cos(l), Math.cos(p) * Math.sin(l), Math.sin(p)];
  const o = ecef(lat, lon, 0);
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  return new THREE.Matrix4().set(
    east[0], east[1], east[2], -dot(east, o),
    up[0], up[1], up[2], -dot(up, o),
    -north[0], -north[1], -north[2], dot(north, o),
    0, 0, 0, 1,
  );
}

export async function mountCity3D(host, lat, lon, { onStatus = () => {}, signal } = {}) {
  const response = await fetch(`/api/vexcel3d/place?lat=${lat}&lon=${lon}`, { cache: "no-store", signal });
  const place = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(place.detail || "3D Cities is unavailable here.");
  if (!place.tiles?.length) throw Error("No Vexcel 3D Cities coverage at this place.");

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.className = "ob-3d-canvas";
  host.append(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1b2023);
  const camera = new THREE.PerspectiveCamera(42, 1, 1, 6000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.49;
  const city = new THREE.Group();
  city.matrixAutoUpdate = false;
  // 3D Tiles glTF is Y-up: rotate it back to Earth-centred Z-up (as Cesium does), then into the local frame.
  city.matrix.copy(localFrame(lat, lon)).multiply(new THREE.Matrix4().makeRotationX(Math.PI / 2));
  scene.add(city);

  const draco = new DRACOLoader().setDecoderPath("./vendor/three/addons/libs/draco/gltf/");
  const ktx2 = new KTX2Loader().setTranscoderPath("./vendor/three/addons/libs/basis/").detectSupport(renderer);
  const loader = new GLTFLoader().setDRACOLoader(draco).setKTX2Loader(ktx2);
  let disposed = false;
  let frame = 0;
  const render = () => {
    if (disposed || frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (controls.update()) render();
      renderer.render(scene, camera);
    });
  };
  controls.addEventListener("change", render);
  const size = () => {
    const w = host.clientWidth || 800, h = host.clientHeight || 533;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    render();
  };
  const observer = new ResizeObserver(size);
  observer.observe(host);
  size();

  const unlit = (object) =>
    object.traverse((node) => {
      if (!node.isMesh) return;
      const old = node.material;
      node.material = new THREE.MeshBasicMaterial({ map: old.map || null, color: old.map ? 0xffffff : 0x8a8f8d });
      old.dispose();
    });

  let loaded = 0;
  let framed = false;

  // The pin stands on the actual surface at the place: a ray cast straight down through the city mesh
  // finds the roof or ground there. The stem and the ring on the surface are hidden by buildings in
  // front, like any real object; only the small head draws over everything, so the place stays findable.
  const amber = 0xedbd69;
  const pin = new THREE.Group();
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 14, 12), new THREE.MeshBasicMaterial({ color: amber }));
  stem.position.y = 7;
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(2.2, 20, 14),
    new THREE.MeshBasicMaterial({ color: amber, depthTest: false, transparent: true, opacity: 0.95 }),
  );
  head.position.y = 15.5;
  head.renderOrder = 10;
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(2.6, 3.6, 40),
    new THREE.MeshBasicMaterial({ color: amber, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -4 }),
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.25;
  pin.add(stem, head, ring);
  pin.visible = false;
  scene.add(pin);
  const ray = new THREE.Raycaster();
  const down = new THREE.Vector3(0, -1, 0);

  const anchor = (box) => {
    ray.set(new THREE.Vector3(0, box.max.y + 50, 0), down);
    const hit = ray.intersectObject(city, true)[0];
    pin.position.set(0, hit ? hit.point.y : box.min.y, 0);
    pin.visible = true;
    return pin.position.y;
  };

  const frameView = () => {
    city.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(city);
    if (box.isEmpty()) return;
    const surface = anchor(box);
    if (!framed) {
      const span = Math.max(box.max.x - box.min.x, box.max.z - box.min.z);
      controls.target.set(0, surface, 0);
      const d = Math.max(140, span * 0.75);
      camera.position.set(d * 0.55, surface + d * 0.62, d * 0.65); // from the south-east, about 40 degrees down
      camera.near = 1;
      camera.far = d * 12;
      camera.updateProjectionMatrix();
      framed = true;
    } else {
      // The centre tile may arrive after the first framing: follow the surface by moving the camera and
      // its target together, so the viewing angle stays the same.
      const shift = surface - controls.target.y;
      controls.target.y += shift;
      camera.position.y += shift;
    }
    controls.update();
    render();
  };

  const queue = [...place.tiles];
  const worker = async () => {
    while (queue.length && !disposed) {
      const url = queue.shift();
      try {
        const gltf = await loader.loadAsync(url);
        if (disposed) return;
        unlit(gltf.scene);
        city.add(gltf.scene);
      } catch {
        /* a missing tile leaves a gap; the rest of the city still loads */
      }
      loaded += 1;
      onStatus(`Loading Vexcel 3D Cities · ${loaded}/${place.tiles.length} tiles`);
      if (loaded === Math.min(4, place.tiles.length) || loaded === place.tiles.length) frameView();
      else render();
    }
  };
  await Promise.all(Array.from({ length: 6 }, worker));
  if (!disposed) onStatus("");

  return {
    place,
    dispose() {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      scene.traverse((node) => {
        node.geometry?.dispose();
        if (node.material) {
          node.material.map?.dispose();
          node.material.dispose();
        }
      });
      draco.dispose();
      ktx2.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
