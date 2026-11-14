const $ = (s) => document.querySelector(s),
  query = $("#query"),
  status = $("#status"),
  results = $("#results"),
  submit = $("#submit");
const picks = new Map();
let searchSerial = 0,
  planSerial = 0;
function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function button(text, fn) {
  const b = el("button", text);
  b.type = "button";
  b.onclick = fn;
  return b;
}
function addPick(s, setup) {
  if (picks.size >= 24 && !picks.has(s.shot_id)) {
    status.textContent = "Lookbook limit: 24 views.";
    return;
  }
  const previous = picks.get(s.shot_id);
  picks.set(s.shot_id, {
    shot: s,
    scene: previous?.scene ?? query.value,
    notes: previous?.notes ?? "",
    setup: setup || previous?.setup || null,
  });
  $("#bookToggle").textContent = `Scene lookbook (${picks.size})`;
  renderBook();
}
async function run(example) {
  const serial = ++searchSerial;
  submit.disabled = true;
  status.textContent = "Searching actual image embeddings…";
  results.replaceChildren();
  try {
    const t = performance.now(),
      p = new URLSearchParams({
        q: query.value,
        diverse: $("#diverse").checked,
        mood: $("#mood").value,
        lighting: $("#lighting").value,
        materials: $("#materials").value,
      });
    if (example) p.set("example", example);
    const r = await fetch("/api/search?" + p);
    if (!r.ok) throw Error("The local interior index is unavailable.");
    const d = await r.json();
    if (serial !== searchSerial) return;
    status.textContent = `${d.mode.toUpperCase()} · ${d.indexed_views} views / ${d.properties} properties · ${d.shots.length} results · ${d.ranking} · ${((performance.now() - t) / 1000).toFixed(2)}s`;
    for (const s of d.shots) {
      s.source_mode = d.mode;
      const card = el("article", undefined, "card"),
        img = el("img");
      img.src = "/image/" + encodeURIComponent(s.shot_id);
      img.alt = s.context.classification || "Interior camera view";
      img.loading = "lazy";
      card.append(img);
      const body = el("div", undefined, "body");
      body.append(
        el(
          "div",
          `SIMILARITY ${Number(s.score).toFixed(3)} · FIT UNKNOWN`,
          "meta",
        ),
        el("h2", s.context.classification || "Interior camera view"),
      );
      body.append(
        el(
          "div",
          `${s.room_area_m2 === null ? "Area unknown" : s.room_area_m2.toFixed(1) + " m² estimated"} · ${s.ceiling_m === null ? "Ceiling unknown" : s.ceiling_m.toFixed(1) + " m ceiling estimated"}`,
          "facts",
        ),
        el(
          "div",
          `Property ${s.property_id} · Scan ${s.sweep_id.slice(0, 10)}…`,
          "facts",
        ),
      );
      const actions = el("div", undefined, "actions");
      actions.append(
        button("Plan lens & clearance", () => openPlan(s)),
        button("Add to lookbook", () => addPick(s)),
        button("Similar elsewhere ↗", () => run(s.shot_id)),
      );
      body.append(actions);
      card.append(body);
      results.append(card);
    }
    if (!d.shots.length) status.textContent += " · No qualifying views.";
  } catch (e) {
    if (serial === searchSerial) status.textContent = e.message;
  } finally {
    if (serial === searchSerial) submit.disabled = false;
  }
}
function field(label, node) {
  const l = el("label", label);
  l.append(node);
  return l;
}
function numberInput(value, min, max, step) {
  const n = el("input");
  n.type = "number";
  Object.assign(n, { value, min, max, step });
  return n;
}
function drawPlan(p) {
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    "Estimated room boundary and manually oriented camera field of view",
  );
  if (!p.ring) {
    return el(
      "p",
      "No validated room boundary at this scan. Lens calculation remains available.",
      "notice",
    );
  }
  const xs = p.ring.map((x) => x[0]),
    ys = p.ring.map((x) => x[1]),
    cx = (Math.min(...xs) + Math.max(...xs)) / 2,
    cy = (Math.min(...ys) + Math.max(...ys)) / 2,
    span =
      Math.max(
        Math.max(...xs) - Math.min(...xs),
        Math.max(...ys) - Math.min(...ys),
      ) * 1.2;
  svg.setAttribute(
    "viewBox",
    `${cx - span / 2} ${-cy - span / 2} ${span} ${span}`,
  );
  function shape(tag, attrs) {
    const n = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    svg.append(n);
  }
  shape("polygon", {
    points: p.ring.map((v) => `${v[0]},${-v[1]}`).join(" "),
    fill: "#243830",
    stroke: "#89a095",
    "stroke-width": span / 200,
  });
  const a = (p.heading_deg * Math.PI) / 180,
    origin = p.position;
  const ends = p.subject_endpoints;
  shape("polygon", {
    points: [origin, ...ends].map((v) => `${v[0]},${-v[1]}`).join(" "),
    fill: p.estimated_clearance ? "#b5ed9244" : "#efb16a44",
    stroke: "#b5ed92",
    "stroke-width": span / 220,
  });
  shape("circle", {
    cx: origin[0],
    cy: -origin[1],
    r: span / 70,
    fill: "#b5ed92",
  });
  return svg;
}
async function openPlan(s) {
  const dialog = $("#planner"),
    body = $("#planBody");
  body.replaceChildren(el("h2", "Plan the camera setup"));
  const grid = el("div", undefined, "planGrid"),
    left = el("div"),
    right = el("div"),
    img = el("img");
  img.src = "/image/" + encodeURIComponent(s.shot_id);
  img.alt = "Selected scouting view";
  left.append(img);
  const focal = numberInput(24, 8, 200, 1),
    width = numberInput(3, 0.1, 30, 0.1),
    heading = numberInput(0, 0, 359, 1),
    sensor = el("select");
  for (const [name, value] of [
    ["Super 35 · 24.9 mm", 24.9],
    ["Full frame · 36 mm", 36],
  ]) {
    const o = el("option", name);
    o.value = value;
    sensor.append(o);
  }
  left.append(
    field("Lens · focal length (mm)", focal),
    field("Sensor width", sensor),
    field("Desired frame width at subjects (m)", width),
    field("Manual plan heading · 0° = +X, 90° = +Y", heading),
  );
  const evidence = el("div"),
    tour = el("a", "Explore source 3D tour ↗");
  tour.href =
    "https://my.matterport.com/show/?m=" + encodeURIComponent(s.model_id);
  tour.target = "_blank";
  tour.rel = "noopener noreferrer";
  left.append(
    tour,
    button("Connect interactive 3D viewer", () =>
      connectTour(s, left, () => latest),
    ),
  );
  right.append(evidence);
  grid.append(left, right);
  body.append(grid);
  if (!dialog.open) dialog.showModal();
  let latest = null;
  async function update() {
    const serial = ++planSerial;
    try {
      for (const n of [focal, width, heading]) if (!n.checkValidity()) return;
      const p = new URLSearchParams({
        focal: focal.value,
        width: width.value,
        heading: heading.value,
        sensor: sensor.value,
      });
      const r = await fetch(
        "/api/plan/" + encodeURIComponent(s.shot_id) + "?" + p,
      );
      if (!r.ok) throw Error("Planning evidence unavailable.");
      const d = await r.json();
      if (serial !== planSerial || !dialog.open) return;
      latest = d;
      evidence.replaceChildren(
        drawPlan(d),
        el(
          "h3",
          `${d.horizontal_fov_deg.toFixed(1)}° horizontal field of view`,
        ),
        el(
          "p",
          `${d.camera_distance_m.toFixed(2)} m camera-to-subject distance · ${d.forward_m === null ? "forward boundary unknown" : d.forward_m.toFixed(2) + " m to forward boundary"} · ${d.backward_m === null ? "rear boundary unknown" : d.backward_m.toFixed(2) + " m to rear boundary"}`,
        ),
        el("p", d.note, "notice"),
        el(
          "p",
          "Clearance test uses 2 m behind subjects and 1 m behind camera. Ceiling is a separate provider estimate; no furniture or rig collision model.",
          "notice",
        ),
        button("Save setup to lookbook", () => addPick(s, latest)),
      );
    } catch (e) {
      evidence.replaceChildren(el("p", e.message));
    }
  }
  for (const n of [focal, width, heading, sensor]) n.onchange = update;
  await update();
}
$("#closePlan").onclick = () => {
  $("#planner").close();
  planSerial++;
};
function renderBook() {
  const host = $("#book");
  host.replaceChildren(
    el("h2", "Scene lookbook"),
    el(
      "p",
      "Compare selected views, record creative intent, and keep source facts beside every setup.",
      "notice",
    ),
  );
  host.append(
    button("Export self-contained lookbook", exportBook),
    button("Export editable JSON", () =>
      download(
        "typecast-lookbook.json",
        JSON.stringify([...picks.values()], null, 2),
        "application/json",
      ),
    ),
  );
  for (const [id, p] of picks) {
    const row = el("div", undefined, "bookRow"),
      img = el("img"),
      info = el("div");
    img.src = "/image/" + encodeURIComponent(id);
    img.alt = "Selected lookbook view";
    const scene = el("input");
    scene.value = p.scene;
    scene.setAttribute("aria-label", "Scene name");
    scene.onchange = () => (p.scene = scene.value);
    const notes = el("textarea");
    notes.value = p.notes;
    notes.placeholder =
      "Creative intent, dressing changes, questions for location scout";
    notes.setAttribute("aria-label", "Scout notes");
    notes.onchange = () => (p.notes = notes.value);
    info.append(
      scene,
      notes,
      el(
        "p",
        `Property ${p.shot.property_id} · ${p.setup ? p.setup.focal_mm + " mm / manual " + p.setup.heading_deg + "°" : "No lens setup saved"} · Fit unverified`,
        "notice",
      ),
      button("Remove", () => {
        picks.delete(id);
        $("#bookToggle").textContent = `Scene lookbook (${picks.size})`;
        renderBook();
      }),
    );
    row.append(img, info);
    host.append(row);
  }
}
function download(name, data, type) {
  const url = URL.createObjectURL(new Blob([data], { type })),
    a = el("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const escapeHtml = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
// Images are embedded so the saved book opens without the local server.
async function exportBook() {
  if (!picks.size) {
    status.textContent = "Select at least one view first.";
    return;
  }
  status.textContent = "Bundling selected images into lookbook…";
  try {
    const cards = [];
    for (const p of picks.values()) {
      const r = await fetch("/image/" + encodeURIComponent(p.shot.shot_id));
      if (!r.ok) throw Error("Selected image unavailable");
      const blob = await r.blob(),
        data = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      const s = p.shot;
      cards.push(
        `<article><h2>${escapeHtml(p.scene)}</h2><img src="${data}"><p>${escapeHtml(p.notes)}</p><p>Property ${escapeHtml(s.property_id)} · Model ${escapeHtml(s.model_id)} · Scan ${escapeHtml(s.sweep_id)}</p><p>${escapeHtml(s.source_mode)} data · Similarity ${Number(s.score).toFixed(3)} · Area ${escapeHtml(s.room_area_m2 ?? "unknown")} m² / ceiling ${escapeHtml(s.ceiling_m ?? "unknown")} m (provider estimates)</p><p>${p.setup ? escapeHtml(`${p.setup.focal_mm} mm, sensor ${p.setup.sensor_width_mm} mm, FOV ${p.setup.horizontal_fov_deg.toFixed(1)}°, subject width ${p.setup.frame_width_m} m, distance ${p.setup.camera_distance_m.toFixed(2)} m, manual plan heading ${p.setup.heading_deg}°. ${p.setup.note}`) : "No lens setup recorded. Fit unverified."}</p></article>`,
      );
    }
    download(
      "typecast-lookbook.html",
      `<!doctype html><meta charset="utf-8"><title>Typecast scene lookbook</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;background:#111719;color:#eaf0ed}main{display:grid;grid-template-columns:1fr 1fr;gap:30px}img{width:100%}article{break-inside:avoid;border:1px solid #567;padding:16px}p{white-space:pre-wrap;font-size:13px}@media print{body{background:white;color:black}main{display:block}article{margin:20px 0}}</style><h1>Typecast / Scene lookbook</h1><p>Created ${escapeHtml(new Date().toISOString())}. Scouting evidence and estimates. Manual headings do not establish panorama alignment. Verify dimensions, access, obstructions and rigging on site.</p><main>${cards.join("")}</main>`,
      "text/html",
    );
    status.textContent = "Lookbook exported with embedded images.";
  } catch (e) {
    status.textContent =
      "Could not export all selected images. The lookbook remains available here.";
  }
}
$("#bookToggle").onclick = () => {
  $("#book").hidden = !$("#book").hidden;
  renderBook();
};
$("#search").onsubmit = (e) => {
  e.preventDefault();
  run();
};
document.querySelectorAll("[data-q]").forEach(
  (b) =>
    (b.onclick = () => {
      query.value = b.dataset.q;
      run();
    }),
);

async function connectTour(shot, host, getSetup) {
  const message = el("p", "Connecting SDK…", "notice");
  host.append(message);
  try {
    const config = await (await fetch("/api/viewer-config")).json();
    if (!config.sdk_key)
      throw Error("SDK key unavailable. The source tour link remains usable.");
    if (location.hostname === "127.0.0.1") {
      message.replaceChildren(el("a", "Open localhost for the SDK connection"));
      message.firstChild.href = "http://localhost:" + location.port + "/";
      return;
    }
    const iframe = el("iframe");
    iframe.title = "Matterport interactive scout";
    iframe.style = "width:100%;height:380px;border:0;margin-top:18px";
    iframe.allow = "fullscreen";
    const url = new URL("https://my.matterport.com/show");
    url.search = new URLSearchParams({
      m: shot.model_id,
      play: "1",
      applicationKey: config.sdk_key,
    });
    iframe.src = url;
    host.append(iframe);
    const { connect } = await import(
      "https://api.matterport.com/sdk/bootstrap/3.1.0-0-g1cd7e0997a/sdk.es6.js?applicationKey=" +
        encodeURIComponent(config.sdk_key)
    );
    const sdk = await Promise.race([
      connect(iframe),
      new Promise((_, reject) =>
        setTimeout(() => reject(Error("SDK connection timed out.")), 25000),
      ),
    ]);
    message.textContent = "SDK connected. Resolving selected scan identity…";
    let pose = null,
      zoom = 1,
      requestedFov = null;
    const fovStatus = el(
      "p",
      "Waiting for viewer camera projection…",
      "notice",
    );
    host.append(fovStatus);
    sdk.Camera.pose.subscribe((value) => {
      pose = value;
      const scale = pose.projection?.[0];
      if (Number.isFinite(scale) && scale > 0) {
        const achieved = (2 * Math.atan(1 / scale) * 180) / Math.PI;
        fovStatus.textContent =
          `Live viewer horizontal FOV ${achieved.toFixed(1)}°` +
          (requestedFov === null
            ? ""
            : ` · requested ${requestedFov.toFixed(1)}°`);
      }
    });
    sdk.Camera.zoom.subscribe((value) => {
      zoom = value.level;
    });
    const sweeps = new Map();
    sdk.Sweep.data.subscribe({
      onAdded: (id, value) => sweeps.set(id, value),
      onUpdated: (id, value) => sweeps.set(id, value),
      onRemoved: (id) => sweeps.delete(id),
    });
    const move = button("Go to selected scan", async () => {
      try {
        const ids = new Set(
          [shot.sweep_id, shot.context.anchor_id].filter(Boolean),
        );
        const matches = [...sweeps.entries()].filter(([id, v]) =>
          [id, v.sid, v.uuid].some((x) => ids.has(x)),
        );
        if (matches.length !== 1) {
          message.textContent =
            "Selected API scan has no unique SDK ID match. Explore manually; alignment unverified.";
          return;
        }
        const [id] = matches[0];
        await sdk.Sweep.moveTo(id, {});
        const confirmed = await sdk.Camera.getPose();
        message.textContent = [
          id,
          matches[0][1].sid,
          matches[0][1].uuid,
        ].includes(confirmed.sweep)
          ? "Selected scan confirmed by SDK. Image heading alignment remains unverified."
          : "Scan movement completed; awaiting current-scan confirmation. Image heading alignment unverified.";
      } catch (e) {
        console.warn(
          "Typecast navigation failure",
          String(e.message).replaceAll(config.sdk_key, "[redacted]"),
        );
        message.textContent =
          "Scan navigation unavailable. Wait for the tour to load, then retry.";
      }
    });
    host.append(
      move,
      button("Apply planned lens field of view", async () => {
        try {
          const setup = getSetup(),
            projection = pose && pose.projection;
          if (
            !setup ||
            !projection ||
            !Number.isFinite(projection[0]) ||
            projection[0] <= 0
          )
            throw Error();
          const horizontal = (2 * Math.atan(1 / projection[0]) * 180) / Math.PI;
          requestedFov = setup.horizontal_fov_deg;
          await sdk.Camera.zoomTo(
            (zoom * horizontal) / setup.horizontal_fov_deg,
          );
          const actual = await sdk.Camera.getPose();
          const achieved =
            (2 * Math.atan(1 / actual.projection[0]) * 180) / Math.PI;
          message.textContent = `Viewer FOV ${achieved.toFixed(1)}°; requested ${setup.horizontal_fov_deg.toFixed(1)}°. SDK zoom limits may constrain the result. Manual camera orientation; image alignment unverified.`;
        } catch (e) {
          message.textContent =
            "Lens field of view unavailable in the current tour mode.";
        }
      }),
      button("Save current 3D camera pose", () => {
        if (!pose) {
          message.textContent = "Camera pose unavailable.";
          return;
        }
        const setup = getSetup();
        addPick(shot, {
          ...setup,
          sdk_pose: {
            position: pose.position,
            rotation: pose.rotation,
            sweep: pose.sweep,
            horizontal_fov_deg:
              (2 * Math.atan(1 / pose.projection[0]) * 180) / Math.PI,
          },
          sdk_pose_captured_at: new Date().toISOString(),
        });
        message.textContent =
          "Current SDK camera pose saved to lookbook JSON. Cube-image alignment remains unverified.";
      }),
    );
    message.textContent =
      "SDK connected. Use selected-scan navigation; panorama heading is not inferred from face number.";
  } catch (e) {
    message.textContent =
      "Interactive SDK unavailable. Use the source tour link; camera alignment is unverified.";
  }
}
