// Typecast viewfinder: stand at the real scan point and frame the shot.
// Four cube faces per scan point (scan-relative headings 0/90/180/270) render as a
// 360-degree band in WebGL2. Lens maths uses a Super 35 sensor. Floor and ceiling
// were not scanned, so tilt is limited and unscanned areas stay visibly empty.

const SENSOR_MM = 24.89;
const LENSES = [14, 18, 24, 35, 50];
const ASPECTS = [
  { id: "2.39", label: "2.39", ratio: 2.39 },
  { id: "1.85", label: "1.85", ratio: 1.85 },
  { id: "1.78", label: "16:9", ratio: 16 / 9 },
];
const FRAME_FRACTION = 0.74; // preferred share of the canvas width for the frame lines
const DATA_HALF_ANGLE = 35; // degrees of vertical scan coverage that is safe at face seams
const STORE_KEY = "typecast.shotlist.v1";
const EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)";
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

const ICON_LOOK = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 3.5v4.2M20.5 12h-4.2M12 20.5v-4.2M3.5 12h4.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/></svg>`;
const ICON_CLOSE = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
const ICON_DRESS = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M18.5 15.5l.8 1.9 1.9.8-1.9.8-.8 1.9-.8-1.9-1.9-.8 1.9-.8z" fill="currentColor"/></svg>`;
const ICON_GRAB = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 8.5V6a2 2 0 0 1 2-2h2.5M15.5 4H18a2 2 0 0 1 2 2v2.5M20 15.5V18a2 2 0 0 1-2 2h-2.5M8.5 20H6a2 2 0 0 1-2-2v-2.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.7"/></svg>`;

const hfovForLens = (mm) => 2 * Math.atan(SENSOR_MM / (2 * mm));
const deg = (rad) => (rad * 180) / Math.PI;
const rad = (d) => (d * Math.PI) / 180;
const wrap360 = (d) => ((d % 360) + 360) % 360;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function shotIdFromSrc(src) {
  try {
    const path = new URL(src, location.href).pathname;
    const match = path.match(/\/cache\/views\/([A-Za-z0-9._-]+)\.(?:jpe?g|png|webp)$/i);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

function addressFromAlt(alt) {
  const at = (alt || "").lastIndexOf(" at ");
  return at >= 0 ? alt.slice(at + 4) : "";
}

function loadShotList() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.slice(0, 12) : [];
  } catch {
    return [];
  }
}

function saveShotList(list) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(list.slice(0, 12)));
  } catch {
    /* storage can be unavailable; the list still works for this visit */
  }
}

/* ---------------- WebGL2 renderer ---------------- */

const VERT = `#version 300 es
in vec2 p;
out vec2 v;
void main() { v = p; gl_Position = vec4(p, 0.0, 1.0); }`;

const FRAG = `#version 300 es
precision highp float;
in vec2 v;
out vec4 color;
uniform sampler2D f0;
uniform sampler2D f1;
uniform sampler2D f2;
uniform sampler2D f3;
uniform vec4 loaded;
uniform float yaw;
uniform float pitch;
uniform float tx;
uniform float ty;
uniform float lod;
uniform sampler2D d0;
uniform sampler2D d1;
uniform sampler2D d2;
uniform sampler2D d3;
uniform vec4 dLoaded;
uniform vec4 dYaw;
uniform vec4 dTanH;
uniform vec4 dTanV;
uniform float wipe;
uniform float dlod;
const float QUARTER = 1.5707963268;
float angDist(float a, float b) { return abs(mod(a - b + 3.14159265, 6.28318531) - 3.14159265); }
vec3 rotY(vec3 d, float a) { return vec3(d.x * cos(a) - d.z * sin(a), d.y, d.x * sin(a) + d.z * cos(a)); }
vec3 rotX(vec3 d, float a) { return vec3(d.x, d.y * cos(a) - d.z * sin(a), d.y * sin(a) + d.z * cos(a)); }
void main() {
  vec3 d = normalize(vec3(v.x * tx, v.y * ty, -1.0));
  d = rotY(rotX(d, pitch), yaw);
  float h = atan(d.x, -d.z);
  float idx = mod(floor((h + 0.7853981634) / QUARTER), 4.0);
  vec3 l = rotY(d, -idx * QUARTER);
  vec2 uv = vec2(0.5 + 0.5 * l.x / -l.z, 0.5 - 0.5 * l.y / -l.z);
  vec2 cuv = clamp(uv, vec2(0.0005), vec2(0.9995));
  vec3 c; float has;
  if (idx < 0.5) { c = textureLod(f0, cuv, lod).rgb; has = loaded.x; }
  else if (idx < 1.5) { c = textureLod(f1, cuv, lod).rgb; has = loaded.y; }
  else if (idx < 2.5) { c = textureLod(f2, cuv, lod).rgb; has = loaded.z; }
  else { c = textureLod(f3, cuv, lod).rgb; has = loaded.w; }
  float elev = abs(asin(clamp(d.y, -1.0, 1.0)));
  vec3 none = vec3(0.071, 0.082, 0.086) * (1.0 - 0.45 * elev / QUARTER);
  float band = smoothstep(0.0, 0.025, uv.y) * (1.0 - smoothstep(0.975, 1.0, uv.y));
  vec3 real = mix(none, c, band * has);
  if (v.x < wipe) {
    // AI-dressed frames: pick the frame whose real Atlas camera heading is nearest.
    float best = angDist(h, dYaw.x); float sel = 0.0;
    float a1 = angDist(h, dYaw.y); if (a1 < best) { best = a1; sel = 1.0; }
    float a2 = angDist(h, dYaw.z); if (a2 < best) { best = a2; sel = 2.0; }
    float a3 = angDist(h, dYaw.w); if (a3 < best) { best = a3; sel = 3.0; }
    float yw = sel < 0.5 ? dYaw.x : sel < 1.5 ? dYaw.y : sel < 2.5 ? dYaw.z : dYaw.w;
    float th = sel < 0.5 ? dTanH.x : sel < 1.5 ? dTanH.y : sel < 2.5 ? dTanH.z : dTanH.w;
    float tv = sel < 0.5 ? dTanV.x : sel < 1.5 ? dTanV.y : sel < 2.5 ? dTanV.z : dTanV.w;
    float ok = sel < 0.5 ? dLoaded.x : sel < 1.5 ? dLoaded.y : sel < 2.5 ? dLoaded.z : dLoaded.w;
    vec3 dl = rotY(d, -yw);
    vec2 duv = vec2(0.5 + 0.5 * (dl.x / -dl.z) / th, 0.5 - 0.5 * (dl.y / -dl.z) / tv);
    vec2 cd = clamp(duv, vec2(0.0005), vec2(0.9995));
    vec3 dc;
    if (sel < 0.5) dc = textureLod(d0, cd, dlod).rgb;
    else if (sel < 1.5) dc = textureLod(d1, cd, dlod).rgb;
    else if (sel < 2.5) dc = textureLod(d2, cd, dlod).rgb;
    else dc = textureLod(d3, cd, dlod).rgb;
    float inside = step(0.0, duv.x) * step(duv.x, 1.0) * step(dl.z, 0.0)
                 * smoothstep(0.0, 0.03, duv.y) * (1.0 - smoothstep(0.97, 1.0, duv.y));
    // Outside the dressed coverage the real room shows, dimmed, so the boundary stays honest.
    real = mix(real * 0.45, dc, inside * ok);
  }
  color = vec4(real, 1.0);
}`;

function createRenderer(canvas) {
  const gl = canvas.getContext("webgl2", {
    antialias: false,
    preserveDrawingBuffer: true,
    powerPreference: "high-performance",
  });
  if (!gl) return null;
  const compile = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader");
    return s;
  };
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl.VERTEX_SHADER, VERT));
  gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAG));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error("link");
  gl.useProgram(program);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(program, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const u = Object.fromEntries(
    ["f0", "f1", "f2", "f3", "loaded", "yaw", "pitch", "tx", "ty", "lod",
      "d0", "d1", "d2", "d3", "dLoaded", "dYaw", "dTanH", "dTanV", "wipe", "dlod"].map((n) => [n, gl.getUniformLocation(program, n)]),
  );
  const aniso = gl.getExtension("EXT_texture_filter_anisotropic");
  const loadedFlags = [0, 0, 0, 0];
  const textures = [0, 1, 2, 3].map((i) => {
    const t = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0 + i);
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([18, 21, 22, 255]));
    gl.uniform1i(u[`f${i}`], i);
    return t;
  });
  let faceSize = 2048;
  const dressedTextures = [4, 5, 6, 7].map((unit, i) => {
    const t = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([18, 21, 22, 255]));
    gl.uniform1i(u[`d${i}`], unit);
    return t;
  });
  const dressed = { loaded: [0, 0, 0, 0], yaw: [0, 0, 0, 0], tanH: [1, 1, 1, 1], tanV: [1, 1, 1, 1], width: 1280 };
  return {
    setDressedFace(i, image, meta) {
      gl.activeTexture(gl.TEXTURE4 + i);
      gl.bindTexture(gl.TEXTURE_2D, dressedTextures[i]);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      if (aniso) gl.texParameterf(gl.TEXTURE_2D, aniso.TEXTURE_MAX_ANISOTROPY_EXT, 8);
      dressed.loaded[i] = 1;
      dressed.yaw[i] = rad(meta.yaw_deg);
      dressed.tanH[i] = meta.tan_h;
      dressed.tanV[i] = meta.tan_v;
      dressed.width = image.naturalWidth || dressed.width;
    },
    setFace(i, image) {
      gl.activeTexture(gl.TEXTURE0 + i);
      gl.bindTexture(gl.TEXTURE_2D, textures[i]);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      if (aniso) gl.texParameterf(gl.TEXTURE_2D, aniso.TEXTURE_MAX_ANISOTROPY_EXT, 8);
      faceSize = image.naturalWidth || faceSize;
      loadedFlags[i] = 1;
    },
    draw({ yaw, pitch, tx, wipe = -1 }) {
      const w = canvas.width;
      const h = canvas.height;
      gl.viewport(0, 0, w, h);
      gl.uniform4f(u.loaded, ...loadedFlags);
      gl.uniform1f(u.yaw, rad(yaw));
      gl.uniform1f(u.pitch, rad(pitch));
      gl.uniform1f(u.tx, tx);
      gl.uniform1f(u.ty, (tx * h) / w);
      // Texels per screen pixel decides the mip level, computed once so face seams stay sharp.
      gl.uniform1f(u.lod, Math.max(0, Math.log2((faceSize * tx) / w)));
      gl.uniform4f(u.dLoaded, ...dressed.loaded);
      gl.uniform4f(u.dYaw, ...dressed.yaw);
      gl.uniform4f(u.dTanH, ...dressed.tanH);
      gl.uniform4f(u.dTanV, ...dressed.tanV);
      gl.uniform1f(u.wipe, wipe);
      gl.uniform1f(u.dlod, Math.max(0, Math.log2((dressed.width * tx) / (dressed.tanH[0] * w))));
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    },
    dispose() {
      textures.forEach((t) => gl.deleteTexture(t));
      dressedTextures.forEach((t) => gl.deleteTexture(t));
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      // Reuse this canvas on the next open; explicitly losing its context prevents that.
    },
  };
}

/* ---------------- Viewfinder dialog ---------------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function buildDialog() {
  const dialog = el("dialog", "vf");
  dialog.setAttribute("aria-label", "Viewfinder: look around the scanned room");
  dialog.innerHTML = `
    <div class="vf-stage">
      <canvas class="vf-canvas" aria-hidden="true"></canvas>
      <img class="vf-poster" alt="" decoding="async" />
      <div class="vf-frame" aria-hidden="true">
        <span class="vf-corner tl"></span><span class="vf-corner tr"></span>
        <span class="vf-corner bl"></span><span class="vf-corner br"></span>
        <span class="vf-center"></span>
        <span class="vf-flash"></span>
        <div class="vf-monitor">
          <span class="vf-m-lens"></span>
          <span class="vf-m-need">
            <span class="vf-dist"></span>
            <span class="vf-width">
              <button type="button" class="vf-step" data-step="-1" aria-label="Narrower frame">−</button>
              <output class="vf-width-value"></output>
              <button type="button" class="vf-step" data-step="1" aria-label="Wider frame">+</button>
            </span>
            <span class="vf-depth"></span>
          </span>
          <span class="vf-m-room"></span>
        </div>
      </div>
      <p class="vf-gap-note">Floor and ceiling weren't scanned</p>
    </div>
    <div class="vf-wipe" hidden>
      <span class="vf-wipe-line"></span>
      <span class="vf-wipe-tag left">AI-dressed</span>
      <span class="vf-wipe-tag right">Real scan</span>
      <button type="button" class="vf-wipe-handle" aria-label="Drag to compare the AI-dressed set with the real scan"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 7l-5 5 5 5M15 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
    </div>
    <p class="vf-ai-badge" hidden></p>
    <header class="vf-top vf-hud">
      <div class="vf-title">
        <span class="vf-brand">Viewfinder</span>
        <span class="vf-address"></span>
      </div>
      <div class="vf-status" role="status" aria-live="polite"></div>
      <button type="button" class="vf-dress" hidden aria-pressed="false">${ICON_DRESS}<span>AI dressing</span><kbd>D</kbd></button>
      <button type="button" class="vf-close" aria-label="Close viewfinder">${ICON_CLOSE}<span>Esc</span></button>
    </header>
    <div class="vf-tape vf-hud" aria-hidden="true"><div class="vf-tape-strip"></div><span class="vf-tape-needle"></span></div>
    <footer class="vf-bottom vf-hud">
      <div class="vf-group">
        <span class="vf-label">Lens</span>
        <div class="vf-lenses" role="group" aria-label="Lens focal length"></div>
      </div>
      <div class="vf-group">
        <span class="vf-label">Frame</span>
        <div class="vf-aspects" role="group" aria-label="Frame aspect ratio"></div>
      </div>
      <button type="button" class="vf-grab">${ICON_GRAB}<span>Grab frame</span><kbd>G</kbd></button>
    </footer>
    <aside class="vf-shotlist vf-hud" aria-label="Shot list">
      <div class="vf-shotlist-head"><span class="vf-label">Shot list</span><button type="button" class="vf-clear">Clear</button></div>
      <ol class="vf-shots"></ol>
    </aside>`;
  document.body.append(dialog);
  return dialog;
}

class Viewfinder {
  constructor() {
    this.dialog = buildDialog();
    this.$ = (s) => this.dialog.querySelector(s);
    this.canvas = this.$(".vf-canvas");
    this.poster = this.$(".vf-poster");
    this.frame = this.$(".vf-frame");
    this.state = { yaw: 0, pitch: 0, lens: 24, aspect: ASPECTS[0], frameWidth: 6 };
    this.view = { yaw: 0, pitch: 0, tx: 1 };
    this.fraction = FRAME_FRACTION;
    this.wipe = -1;
    this.dressed = null;
    this.shots = loadShotList();
    this.sweep = null;
    this.renderer = null;
    this.raf = 0;
    this.velocity = 0;
    this.generation = 0;
    this.animating = false;
    this.buildControls();
    this.bindInput();
    this.renderShotList();
  }

  buildControls() {
    const lenses = this.$(".vf-lenses");
    LENSES.forEach((mm) => {
      const b = el("button", "vf-chip", `${mm}`);
      b.type = "button";
      b.dataset.lens = String(mm);
      b.setAttribute("aria-label", `${mm} millimetre lens`);
      b.addEventListener("click", () => this.setLens(mm));
      lenses.append(b);
    });
    const aspects = this.$(".vf-aspects");
    ASPECTS.forEach((a) => {
      const b = el("button", "vf-chip", a.label);
      b.type = "button";
      b.dataset.aspect = a.id;
      b.setAttribute("aria-label", `Aspect ratio ${a.label}`);
      b.addEventListener("click", () => this.setAspect(a));
      aspects.append(b);
    });
    const strip = this.$(".vf-tape-strip");
    for (let d = -360; d <= 720; d += 15) {
      const tick = el("span", d % 90 === 0 ? "vf-tick major" : d % 45 === 0 ? "vf-tick mid" : "vf-tick");
      tick.style.setProperty("--d", String(d + 360));
      if (d % 45 === 0) tick.dataset.label = String(wrap360(d));
      strip.append(tick);
    }
  }

  bindInput() {
    this.$(".vf-close").addEventListener("click", () => this.close());
    this.dialog.addEventListener("cancel", (e) => {
      e.preventDefault();
      this.close();
    });
    this.$(".vf-grab").addEventListener("click", () => this.grab());
    this.$(".vf-dress").addEventListener("click", () => this.toggleDressing());
    const handle = this.$(".vf-wipe-handle");
    handle.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      handle.setPointerCapture(e.pointerId);
      cancelAnimationFrame(this.wipeTween);
      const move = (ev) => {
        const r = this.canvas.getBoundingClientRect();
        this.setWipe(clamp((2 * (ev.clientX - r.left)) / r.width - 1, -0.98, 0.98));
      };
      const up = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
        handle.removeEventListener("pointercancel", up);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
      handle.addEventListener("pointercancel", up);
    });
    handle.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        e.stopPropagation();
        this.setWipe(clamp(this.wipe + (e.key === "ArrowLeft" ? -0.08 : 0.08), -0.98, 0.98));
      }
    });
    this.$(".vf-clear").addEventListener("click", () => {
      this.shots = [];
      saveShotList(this.shots);
      this.renderShotList();
    });
    this.dialog.querySelectorAll(".vf-step").forEach((b) =>
      b.addEventListener("click", () => {
        this.state.frameWidth = clamp(this.state.frameWidth + Number(b.dataset.step), 1, 30);
        this.updateReadout();
      }),
    );
    const stage = this.$(".vf-stage");
    const pointers = new Map();
    let last = null;
    let pinch = null;
    stage.addEventListener("pointerdown", (e) => {
      stage.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      last = { x: e.clientX, y: e.clientY, t: performance.now() };
      this.velocity = 0;
      stage.classList.add("is-dragging");
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        pinch = { dist: Math.hypot(a.x - b.x, a.y - b.y), lens: this.state.lens };
      }
    });
    stage.addEventListener("pointermove", (e) => {
      if (!pointers.has(e.pointerId)) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pinch && pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        const ratio = Math.hypot(a.x - b.x, a.y - b.y) / pinch.dist;
        this.setLens(clamp(pinch.lens * ratio, LENSES[0], LENSES.at(-1)), { instant: true });
        return;
      }
      if (!last) return;
      const degPerPx = deg(2 * Math.atan(this.view.tx)) / stage.clientWidth;
      const dx = e.clientX - last.x;
      const dy = e.clientY - last.y;
      const now = performance.now();
      this.state.yaw = wrap360(this.state.yaw - dx * degPerPx);
      this.state.pitch = this.clampPitch(this.state.pitch + dy * degPerPx);
      this.view.yaw = this.state.yaw;
      this.view.pitch = this.state.pitch;
      this.velocity = (-dx * degPerPx) / Math.max(8, now - last.t);
      last = { x: e.clientX, y: e.clientY, t: now };
      this.kick();
      this.updateReadout();
    });
    const release = (e) => {
      pointers.delete(e.pointerId);
      if (pointers.size < 2) pinch = null;
      if (pointers.size === 0) {
        stage.classList.remove("is-dragging");
        last = null;
        if (!reducedMotion()) this.coast();
      }
    };
    stage.addEventListener("pointerup", release);
    stage.addEventListener("pointercancel", release);
    stage.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        this.setLens(clamp(this.state.lens * Math.exp(-e.deltaY * 0.0015), LENSES[0], LENSES.at(-1)), { instant: true });
      },
      { passive: false },
    );
    this.dialog.addEventListener("keydown", (e) => {
      if (e.target instanceof HTMLButtonElement && (e.key === "Enter" || e.key === " ")) return;
      const step = e.shiftKey ? 15 : 5;
      const keys = {
        ArrowLeft: () => this.turn(-step, 0),
        ArrowRight: () => this.turn(step, 0),
        ArrowUp: () => this.turn(0, 3),
        ArrowDown: () => this.turn(0, -3),
        "[": () => this.stepLens(-1),
        "]": () => this.stepLens(1),
        "-": () => this.stepLens(-1),
        "=": () => this.stepLens(1),
        a: () => this.setAspect(ASPECTS[(ASPECTS.indexOf(this.state.aspect) + 1) % ASPECTS.length]),
        g: () => this.grab(),
        d: () => this.toggleDressing(),
      };
      const action = keys[e.key] || keys[e.key.toLowerCase?.()];
      if (action) {
        e.preventDefault();
        action();
      }
    });
    addEventListener("resize", () => this.dialog.open && this.resize());
  }

  clampPitch(p) {
    const vHalf = deg(Math.atan((this.view.tx * this.canvas.clientHeight) / Math.max(1, this.canvas.clientWidth)));
    const limit = Math.max(0, DATA_HALF_ANGLE - vHalf * 0.55);
    return clamp(p, -limit, limit);
  }

  turn(dyaw, dpitch) {
    this.state.yaw = wrap360(this.state.yaw + dyaw);
    this.state.pitch = this.clampPitch(this.state.pitch + dpitch);
    this.animateTo({ yaw: this.state.yaw, pitch: this.state.pitch }, 220);
  }

  stepLens(dir) {
    const i = LENSES.findIndex((mm) => mm >= this.state.lens - 0.5);
    const next = LENSES[clamp((i < 0 ? LENSES.length - 1 : i) + dir, 0, LENSES.length - 1)];
    this.setLens(next);
  }

  txForLens(mm) {
    // The lens field of view spans the frame lines, not the whole monitor.
    return Math.tan(hfovForLens(mm) / 2) / this.fraction;
  }

  setLens(mm, { instant = false } = {}) {
    this.state.lens = mm;
    const tx = this.txForLens(mm);
    if (instant || reducedMotion()) {
      this.view.tx = tx;
      this.state.pitch = this.clampPitch(this.state.pitch);
      this.view.pitch = this.state.pitch;
      this.kick();
    } else {
      this.animateTo({ tx }, 420);
    }
    this.dialog.querySelectorAll(".vf-lenses .vf-chip").forEach((b) => {
      const active = Math.abs(Number(b.dataset.lens) - mm) < 0.5;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-pressed", String(active));
    });
    this.updateReadout();
  }

  setAspect(aspect) {
    this.state.aspect = aspect;
    this.dialog.querySelectorAll(".vf-aspects .vf-chip").forEach((b) => {
      const active = b.dataset.aspect === aspect.id;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-pressed", String(active));
    });
    this.layoutFrame();
    this.updateReadout();
  }

  layoutFrame() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    const hud = this.$(".vf-bottom").offsetHeight || 84;
    this.dialog.style.setProperty("--hud-h", `${hud}px`);
    // Keep the frame centred on the optical axis and clear of the top bar, readout, tape and controls.
    const below = hud + 22 + 64;
    const maxH = Math.max(140, 2 * Math.min(h / 2 - 124, h / 2 - below));
    let fw = w * FRAME_FRACTION;
    // The shot list sits on the right; the frame stays centred on the optical axis and clears it.
    const tray = this.dialog.classList.contains("has-shots") && w > 900 ? this.$(".vf-shotlist").offsetWidth + 40 : 0;
    if (tray) fw = Math.min(fw, w - 2 * tray);
    let fh = fw / this.state.aspect.ratio;
    if (fh > maxH) {
      fh = maxH;
      fw = fh * this.state.aspect.ratio;
    }
    this.frame.style.width = `${fw}px`;
    this.frame.style.height = `${fh}px`;
    const fraction = fw / Math.max(1, w);
    if (Math.abs(fraction - this.fraction) > 0.0005) {
      const lensBefore = this.state.lens;
      this.fraction = fraction;
      if (this.dialog.classList.contains("is-live")) {
        // Ease the scene with the frame-line transition so the lens framing never jumps.
        this.animateTo({ tx: this.txForLens(lensBefore) }, reducedMotion() ? 1 : 420);
      }
    }
  }

  updateReadout() {
    const hfov = hfovForLens(this.state.lens);
    const width = this.state.frameWidth;
    const distance = width / 2 / Math.tan(hfov / 2);
    const depth = distance + 3;
    const aspect = this.state.aspect;
    this.$(".vf-m-lens").textContent = `${Math.round(this.state.lens)} mm · Super 35 · ${aspect.label}${aspect.id === "1.78" ? "" : " : 1"}`;
    this.$(".vf-width-value").textContent = `${width} m assumed`;
    this.$(".vf-dist").textContent = `Camera ${distance.toFixed(1)} m back to hold`;
    this.$(".vf-depth").textContent = `wide · needs ${depth.toFixed(1)} m of room`;
    const s = this.sweep;
    const facing = s && Math.abs(((this.state.yaw - s.heading_deg + 540) % 360) - 180) < 20;
    let room = "Depth this way unknown · measure on site";
    if (s?.depth_m != null && facing) {
      room = `Depth this way ${s.depth_m.toFixed(1)} m${s.measure_on_site ? " (estimated)" : ""}`;
    }
    if (s?.ceiling_m != null) room += ` · ceiling ${s.ceiling_m.toFixed(1)} m${s.measure_on_site ? " est." : ""}`;
    this.$(".vf-m-room").textContent = room;
    const status = `${Math.round(this.state.lens)} mm · ${this.state.aspect.label} · scan-relative ${Math.round(this.state.yaw)}°`;
    this.$(".vf-status").textContent = status;
  }

  async loadDressed(shotId, generation, renderer) {
    // Same guard as open(): a late response for a closed scan point must never dress the next room.
    const current = () => generation === this.generation && this.renderer === renderer
      && this.dialog.open && !this.dialog.classList.contains("is-closing");
    let data;
    try {
      const r = await fetch(`/api/dressed/${encodeURIComponent(shotId)}`);
      if (!r.ok || !current()) return;
      data = await r.json();
    } catch {
      return;
    }
    if (!current() || !data?.faces?.length) return;
    this.dressed = data;
    const slug = (data.scene || "").match(/^((?:INT\.?\/EXT|INT|EXT)\.\s*[^.]+)/i);
    const scene = (slug ? slug[1] : (data.scene || "").split(".")[0]).trim();
    this.$(".vf-ai-badge").textContent = `${data.label || "AI-imagined set dressing, not the real room"}${scene ? ` · dressed for “${scene}”` : ""}`;
    let loaded = 0;
    await Promise.all(
      data.faces.slice(0, 4).map(async (face, i) => {
        const img = new Image();
        img.decoding = "async";
        img.src = face.dressed_url;
        try {
          await img.decode();
          if (current()) {
            renderer.setDressedFace(i, img, face);
            loaded += 1;
          }
        } catch {
          /* a missing dressed frame leaves the real room visible there */
        }
      }),
    );
    if (!current()) return;
    if (!loaded) {
      // Never offer a comparison with nothing to compare: the toggle would only dim the real room.
      this.dressed = null;
      this.$(".vf-status").textContent = "The AI-dressed frames for this room couldn't load. Reload to get the current set.";
      return;
    }
    const toggle = this.$(".vf-dress");
    toggle.hidden = false;
    if (!reducedMotion()) toggle.animate([{ transform: "scale(0.9)", opacity: 0 }, { transform: "scale(1)", opacity: 1 }], { duration: 420, easing: EASE_OUT });
    this.$(".vf-status").textContent = "An AI-dressed version of this room is ready: press D or AI dressing.";
  }

  setWipe(value) {
    this.wipe = value;
    const on = value > -1;
    this.$(".vf-wipe").hidden = !on;
    this.$(".vf-ai-badge").hidden = !on;
    this.dialog.classList.toggle("is-dressed", on);
    const toggle = this.$(".vf-dress");
    toggle.setAttribute("aria-pressed", String(on));
    toggle.classList.toggle("is-active", on);
    this.kick();
  }

  positionWipe() {
    const wipe = this.$(".vf-wipe");
    if (wipe.hidden) return;
    wipe.style.setProperty("--x", `${((this.wipe + 1) / 2) * this.canvas.clientWidth}px`);
  }

  toggleDressing() {
    if (!this.dressed) return;
    cancelAnimationFrame(this.wipeTween);
    const from = this.wipe;
    const to = from > -1 ? -1 : 0.15;
    if (reducedMotion()) return this.setWipe(to);
    // The dressing sweeps in from the left like a lighting cue, then rests as a comparison.
    const start = performance.now();
    const duration = to > from ? 1100 : 420;
    const step = (now) => {
      const t = clamp((now - start) / duration, 0, 1);
      const k = 1 - Math.pow(1 - t, 3);
      this.setWipe(from + (to - from) * k);
      if (t < 1) this.wipeTween = requestAnimationFrame(step);
    };
    if (from <= -1) this.setWipe(-0.999);
    this.wipeTween = requestAnimationFrame(step);
  }

  updateTape() {
    const strip = this.$(".vf-tape-strip");
    strip.style.setProperty("--yaw", String(this.view.yaw));
  }

  resize() {
    const dpr = Math.min(2, devicePixelRatio || 1);
    const w = Math.round(this.canvas.clientWidth * dpr);
    const h = Math.round(this.canvas.clientHeight * dpr);
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this.layoutFrame();
    this.kick();
  }

  kick() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      this.draw();
    });
  }

  draw() {
    this.renderer?.draw({ ...this.view, wipe: this.wipe });
    this.positionWipe();
    this.updateTape();
    const wide = this.view.tx * (this.canvas.clientHeight / Math.max(1, this.canvas.clientWidth));
    const vEdge = deg(Math.atan(wide)) + Math.abs(this.view.pitch);
    this.dialog.classList.toggle("shows-gap", vEdge > DATA_HALF_ANGLE + 4);
  }

  animateTo(target, duration) {
    this.animating = true;
    const from = { ...this.view };
    const start = performance.now();
    cancelAnimationFrame(this.tween);
    const yawDelta = target.yaw == null ? 0 : ((target.yaw - from.yaw + 540) % 360) - 180;
    const step = (now) => {
      const t = clamp((now - start) / duration, 0, 1);
      const k = 1 - Math.pow(1 - t, 4);
      if (target.tx != null) this.view.tx = from.tx + (target.tx - from.tx) * k;
      if (target.yaw != null) this.view.yaw = wrap360(from.yaw + yawDelta * k);
      if (target.pitch != null) this.view.pitch = from.pitch + (target.pitch - from.pitch) * k;
      this.draw();
      if (t < 1) this.tween = requestAnimationFrame(step);
      else {
        this.animating = false;
        this.tween = 0;
        this.state.pitch = this.clampPitch(this.view.pitch);
        this.view.pitch = this.state.pitch;
        this.updateReadout();
      }
    };
    this.tween = requestAnimationFrame(step);
  }

  coast() {
    cancelAnimationFrame(this.coastRaf);
    let prev = performance.now();
    const step = (now) => {
      const dt = now - prev;
      prev = now;
      this.velocity *= Math.pow(0.9, dt / 16);
      if (Math.abs(this.velocity) < 0.002) return this.updateReadout();
      this.state.yaw = wrap360(this.state.yaw + this.velocity * dt);
      this.view.yaw = this.state.yaw;
      this.draw();
      this.coastRaf = requestAnimationFrame(step);
    };
    this.coastRaf = requestAnimationFrame(step);
  }

  async open(shotId, sourceImage) {
    if (this.dialog.open) return;
    const generation = ++this.generation;
    const current = () => generation === this.generation && this.dialog.open && !this.dialog.classList.contains("is-closing");
    this.sourceImage = sourceImage;
    this.$(".vf-address").textContent = addressFromAlt(sourceImage?.alt) || "Scanned room";
    this.poster.src = sourceImage?.currentSrc || sourceImage?.src || "";
    this.dialog.classList.remove("is-live", "is-closing", "no-webgl");
    this.dialog.showModal();
    this.canvas.style.opacity = "0";
    let sweep;
    try {
      const r = await fetch(`/api/sweep/${encodeURIComponent(shotId)}`);
      if (!r.ok) throw new Error(String(r.status));
      sweep = await r.json();
      if (!current()) return;
    } catch {
      if (!current()) return;
      this.$(".vf-status").textContent = "The 360° view isn't available for this frame.";
      this.dialog.classList.add("no-webgl");
      return;
    }
    this.sweep = sweep;
    this.state.yaw = wrap360(sweep.heading_deg || 0);
    this.state.pitch = 0;
    this.view = { yaw: this.state.yaw, pitch: 0, tx: 1 };
    this.resize();
    this.setAspect(this.state.aspect);
    this.updateReadout();
    try {
      this.renderer = createRenderer(this.canvas);
    } catch {
      this.renderer = null;
    }
    if (!this.renderer) {
      this.dialog.classList.add("no-webgl");
      this.$(".vf-status").textContent = "This browser can't draw the 360° view; showing the captured frame.";
      return;
    }
    const renderer = this.renderer;
    const flight = this.flyIn(sourceImage);
    const faces = await Promise.all(
      [0, 90, 180, 270].map(async (heading, i) => {
        const face = sweep.faces.find((f) => f.heading_deg === heading);
        if (!face) return false;
        const img = new Image();
        img.decoding = "async";
        img.src = face.image_path.startsWith("/") ? face.image_path : `/${face.image_path}`;
        try {
          await img.decode();
          if (!current() || this.renderer !== renderer) return false;
          renderer.setFace(i, img);
          return true;
        } catch {
          return false;
        }
      }),
    );
    await flight;
    if (!current() || this.renderer !== renderer) return;
    this.draw();
    const missing = faces.filter((ok) => !ok).length;
    this.revealLive(missing);
    this.loadDressed(shotId, generation, renderer);
  }

  flyIn(sourceImage) {
    const poster = this.poster;
    const rect = sourceImage?.getBoundingClientRect();
    const stage = this.$(".vf-stage").getBoundingClientRect();
    if (!rect || !rect.width || reducedMotion()) {
      poster.style.transform = "";
      return Promise.resolve();
    }
    // The card shows the whole square face inside a contained box; start from that square.
    const side = Math.min(rect.width, rect.height);
    const startX = rect.left + (rect.width - side) / 2 + side / 2 - (stage.left + stage.width / 2);
    const startY = rect.top + (rect.height - side) / 2 + side / 2 - (stage.top + stage.height / 2);
    const endScale = stage.width / poster.getBoundingClientRect().width || 1;
    const startScale = side / poster.getBoundingClientRect().width || 0.3;
    const anim = poster.animate(
      [
        { transform: `translate(${startX}px, ${startY}px) scale(${startScale})`, borderRadius: "12px" },
        { transform: `translate(0, 0) scale(${endScale})`, borderRadius: "0px" },
      ],
      { duration: 620, easing: EASE_OUT, fill: "forwards" },
    );
    this.dialog.animate([{ backgroundColor: "rgba(9,11,12,0)" }, { backgroundColor: "rgba(9,11,12,1)" }], {
      duration: 420,
      easing: EASE_OUT,
      fill: "forwards",
    });
    return anim.finished.catch(() => {});
  }

  revealLive(missing) {
    this.canvas.style.opacity = "1";
    this.dialog.classList.add("is-live");
    const fade = this.poster.animate([{ opacity: 1 }, { opacity: 0 }], { duration: reducedMotion() ? 1 : 260, fill: "forwards" });
    fade.finished.then(() => (this.poster.style.visibility = "hidden")).catch(() => {});
    // Rack from the full captured face to the working lens: the photo becomes a window.
    this.setLens(this.state.lens);
    if (missing) this.$(".vf-status").textContent = `${missing} of 4 directions weren't captured at this scan point.`;
    this.$(".vf-grab").focus({ preventScroll: true });
  }

  async close() {
    if (!this.dialog.open || this.dialog.classList.contains("is-closing")) return;
    ++this.generation;
    this.dialog.classList.add("is-closing");
    const done = this.dialog.animate([{ opacity: 1 }, { opacity: 0 }], { duration: reducedMotion() ? 1 : 180, easing: "ease-in" });
    await done.finished.catch(() => {});
    cancelAnimationFrame(this.tween);
    cancelAnimationFrame(this.coastRaf);
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    this.animating = false;
    this.renderer?.dispose();
    this.renderer = null;
    this.poster.getAnimations().forEach((a) => a.cancel());
    this.dialog.getAnimations().forEach((a) => a.cancel());
    this.poster.style.visibility = "";
    this.dialog.close();
    this.dialog.classList.remove("is-closing", "is-live", "shows-gap");
    cancelAnimationFrame(this.wipeTween);
    this.dressed = null;
    if (this.wipe > -1) this.setWipe(-1);
    this.$(".vf-dress").hidden = true;
    this.sourceImage?.closest(".shot-stage")?.querySelector(".vf-open")?.focus({ preventScroll: true });
  }

  grab() {
    if (!this.renderer || !this.dialog.open || !this.dialog.classList.contains("is-live") || this.dialog.classList.contains("is-closing")) return;
    if (this.animating) {
      this.$(".vf-status").textContent = "Framing is moving. Grab again when it settles.";
      return;
    }
    this.draw();
    const c = this.canvas;
    const fr = this.frame.getBoundingClientRect();
    const cr = c.getBoundingClientRect();
    const sx = (c.width / cr.width) * (fr.left - cr.left);
    const sy = (c.height / cr.height) * (fr.top - cr.top);
    const sw = (c.width / cr.width) * fr.width;
    const sh = (c.height / cr.height) * fr.height;
    const out = document.createElement("canvas");
    out.width = 480;
    out.height = Math.round(480 / this.state.aspect.ratio);
    out.getContext("2d").drawImage(c, sx, sy, sw, sh, 0, 0, out.width, out.height);
    const shot = {
      id: `${Date.now()}`,
      thumb: out.toDataURL("image/jpeg", 0.82),
      lens: Math.round(this.state.lens),
      aspect: this.state.aspect.id,
      yaw: Math.round(this.state.yaw),
      pitch: Math.round(this.state.pitch),
      shotId: this.sweep?.shot_id,
      address: this.$(".vf-address").textContent,
      ai: this.wipe > -1,
    };
    this.shots = [shot, ...this.shots].slice(0, 12);
    saveShotList(this.shots);
    if (!reducedMotion()) {
      this.$(".vf-flash").animate([{ opacity: 0.7 }, { opacity: 0 }], { duration: 260, easing: "ease-out" });
    }
    this.renderShotList(shot.id);
    this.$(".vf-status").textContent = `Frame grabbed: ${shot.lens} mm, ${this.state.aspect.label}, scan-relative heading ${shot.yaw}°${shot.ai ? ", includes AI dressing" : ""}`;
  }

  renderShotList(freshId) {
    const list = this.$(".vf-shots");
    list.replaceChildren();
    const hadShots = this.dialog.classList.contains("has-shots");
    this.dialog.classList.toggle("has-shots", this.shots.length > 0);
    if (hadShots !== this.shots.length > 0 && this.dialog.open) requestAnimationFrame(() => this.layoutFrame());
    this.shots.forEach((shot, i) => {
      const li = el("li", "vf-shot");
      const button = el("button", "vf-shot-recall");
      button.type = "button";
      button.setAttribute("aria-label", `Recall shot ${i + 1}: ${shot.lens} millimetre, ${shot.aspect}, scan-relative heading ${shot.yaw} degrees`);
      const img = el("img");
      img.src = shot.thumb;
      img.alt = "";
      const place = el("span", "vf-shot-place", shot.address || "Scanned room");
      const meta = el("span", "vf-shot-meta", `${shot.lens} mm · ${ASPECTS.find((a) => a.id === shot.aspect)?.label || shot.aspect} · ${shot.yaw}°${shot.ai ? " · AI-dressed" : ""}`);
      button.append(img, place, meta);
      button.addEventListener("click", () => {
        if (shot.shotId && this.sweep && shot.shotId !== this.sweep.shot_id) {
          this.$(".vf-status").textContent = "That shot was framed at another scan point.";
          return;
        }
        const aspect = ASPECTS.find((a) => a.id === shot.aspect) || ASPECTS[0];
        this.setAspect(aspect);
        this.state.yaw = shot.yaw;
        this.state.pitch = shot.pitch;
        this.state.lens = shot.lens;
        this.animateTo({ yaw: shot.yaw, pitch: shot.pitch, tx: this.txForLens(shot.lens) }, reducedMotion() ? 1 : 520);
        this.setLens(shot.lens, { instant: true });
      });
      const save = el("a", "vf-shot-save", "Save");
      save.href = shot.thumb;
      save.download = `typecast-shot-${shot.lens}mm-${shot.yaw}deg.jpg`;
      li.append(button, save);
      if (shot.id === freshId && !reducedMotion()) {
        li.animate(
          [
            { transform: "translateY(18px) scale(0.92)", opacity: 0 },
            { transform: "translateY(0) scale(1)", opacity: 1 },
          ],
          { duration: 420, easing: EASE_OUT },
        );
      }
      list.append(li);
    });
  }
}

/* ---------------- Attach "Look around" to every real frame ---------------- */

let viewfinder = null;
const getViewfinder = () => (viewfinder ||= new Viewfinder());

function decorate(stage) {
  const img = stage.querySelector("img.shot-image");
  let button = stage.querySelector(":scope > .vf-open");
  const id = img && shotIdFromSrc(img.getAttribute("src") || "");
  if (!id) {
    button?.remove();
    return;
  }
  if (!button) {
    button = el("button", "vf-open");
    button.type = "button";
    button.innerHTML = `${ICON_LOOK}<span>Look around</span>`;
    button.setAttribute("aria-label", "Look around this room in 360 degrees");
    button.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      getViewfinder().open(button.dataset.shotId, stage.querySelector("img.shot-image"));
    });
    stage.append(button);
  }
  button.dataset.shotId = id;
}

let scheduled = false;
function scan() {
  scheduled = false;
  document.querySelectorAll(".shot-stage").forEach(decorate);
}
new MutationObserver(() => {
  if (!scheduled) {
    scheduled = true;
    requestAnimationFrame(scan);
  }
}).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["src"] });
scan();

export { Viewfinder, shotIdFromSrc };
