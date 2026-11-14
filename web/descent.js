import { el, button, assetUrl } from "./utils.js";
import { stageMap } from "./map.js";

const EASE = "cubic-bezier(0.16, 1, 0.3, 1)";
const SVG = "http://www.w3.org/2000/svg";
const finite = (value) => typeof value === "number" && Number.isFinite(value);

function wait(ms, signal) {
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    };
    const timer = setTimeout(done, ms);
    signal.addEventListener("abort", done, { once: true });
    if (signal.aborted) done();
  });
}
function loadImage(path, signal) {
  const src = assetUrl(path);
  if (!src || signal.aborted) return Promise.resolve(null);
  return new Promise((resolve) => {
    const image = new Image();
    let timer;
    const done = (value = null) => {
      clearTimeout(timer);
      image.onload = image.onerror = null;
      signal.removeEventListener("abort", aborted);
      resolve(value);
    };
    const aborted = () => done();
    image.onload = () =>
      done(image.naturalWidth && image.naturalHeight ? image : null);
    image.onerror = () => done();
    signal.addEventListener("abort", aborted, { once: true });
    timer = setTimeout(() => done(), 1600);
    image.src = src;
  });
}
async function aerialAssets(pick, signal) {
  const original = pick.logistics?.aerial_image_path;
  if (!assetUrl(original)) return null;
  const fallback = loadImage(original, signal);
  const id = pick.property?.property_id;
  try {
    if (!/^[0-9]{1,12}$/.test(id)) throw Error();
    const response = await fetch(`/api/aerial/${encodeURIComponent(id)}`, {
      signal,
      cache: "no-store",
    });
    if (!response.ok) throw Error();
    const metadata = await response.json();
    const { extent, coordinates, width, height } = metadata;
    if (
      metadata.property_id !== id ||
      metadata.crs !== "EPSG:3857" ||
      metadata.image_path !== `cache/vexcel/${id}/aerial.png` ||
      !Array.isArray(extent) ||
      extent.length !== 4 ||
      !extent.every(finite) ||
      extent[0] >= extent[2] ||
      extent[1] >= extent[3] ||
      !Array.isArray(coordinates) ||
      coordinates.length !== 2 ||
      !coordinates.every(finite) ||
      !finite(pick.property.lat) ||
      !finite(pick.property.lon) ||
      Math.abs(coordinates[0] - pick.property.lat) > 1e-6 ||
      Math.abs(coordinates[1] - pick.property.lon) > 1e-6
    )
      throw Error();
    const image = await loadImage(metadata.image_path, signal);
    if (
      !image ||
      image.naturalWidth !== width ||
      image.naturalHeight !== height
    )
      throw Error();
    const path = parkingPath(pick.logistics, metadata);
    if (!path) throw Error();
    return { image, metadata, path, kind: "projected" };
  } catch {
    const image = await fallback;
    return image ? { image, kind: "existing-image" } : null;
  }
}

/** Match the north-up EPSG:3857 extract; reject rather than guess axes. */
export function parkingPath(logistics, metadata) {
  let rings;
  const geometry = logistics?.parking_geometry;
  if (geometry?.type === "Polygon") rings = geometry.coordinates;
  else if (
    geometry?.type === "MultiPolygon" &&
    Array.isArray(geometry.coordinates)
  )
    rings = geometry.coordinates.flat(1);
  else if (Array.isArray(logistics?.parking_polygon))
    rings = [
      logistics.parking_polygon.map((point) =>
        Array.isArray(point) ? [point[1], point[0]] : point,
      ),
    ];
  if (!Array.isArray(rings) || !rings.length) return null;
  const [west, south, east, north] = metadata.extent;
  let count = 0;
  const paths = [];
  for (const ring of rings) {
    if (!Array.isArray(ring) || ring.length < 3) return null;
    const points = [];
    for (const point of ring) {
      if (++count > 15000 || !Array.isArray(point) || point.length < 2)
        return null;
      const [lon, lat] = point;
      if (
        !finite(lon) ||
        !finite(lat) ||
        Math.abs(lon) > 180 ||
        Math.abs(lat) > 85
      )
        return null;
      const x = (6378137 * lon * Math.PI) / 180;
      const y =
        6378137 * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
      const u = (x - west) / (east - west),
        v = (north - y) / (north - south);
      if (!finite(u) || !finite(v) || u < 0 || u > 1 || v < 0 || v > 1)
        return null;
      points.push(
        `${(u * metadata.width).toFixed(2)},${(v * metadata.height).toFixed(2)}`,
      );
    }
    paths.push(`M${points.join("L")}Z`);
  }
  return paths.join(" ");
}

export class Descent {
  constructor(mapHost) {
    this.mapHost = mapHost;
    this.active = null;
  }
  update(data, { autoplay = true } = {}) {
    this.cancel("superseded", false);
    const card = document.querySelector("#results .pick-card");
    const pick = data.picks?.[0];
    if (!card || !pick?.shots?.[0]?.image_path) return;
    const replay = button(
      "Replay descent",
      () => this.play(data),
      "descent-replay",
    );
    card.querySelector(".pick-actions")?.append(replay);
    if (autoplay) this.play(data);
  }
  notify(run, phase, extra = {}) {
    if (run.stage) run.stage.dataset.phase = phase;
    document.dispatchEvent(
      new CustomEvent("typecast:descent", {
        detail: {
          phase,
          source_mode: run.data.source_mode,
          reducedMotion: run.reduced,
          property_id: run.pick.property.property_id,
          ...extra,
        },
      }),
    );
  }
  animate(run, node, frames, options) {
    if (!node || run.abort.signal.aborted) return null;
    const animation = node.animate(frames, {
      easing: EASE,
      fill: "forwards",
      ...options,
    });
    animation.finished.catch(() => {});
    run.animations.push(animation);
    return animation;
  }
  cancel(outcome = "skipped", land = true) {
    const run = this.active;
    if (!run) return;
    run.transition?.skipTransition();
    this.complete(run, outcome, land && Boolean(run.stage));
  }
  complete(run, outcome, land = true) {
    if (run.done) return;
    run.done = true;
    run.abort.abort();
    run.animations.forEach((animation) => animation.cancel());
    run.borrowed?.restore();
    run.stage?.remove();
    run.listeners.forEach((remove) => remove());
    run.inert?.forEach(([node, value]) => {
      node.inert = value;
    });
    document.body.classList.remove("descent-playing");
    document.documentElement.classList.remove("descent-transition");
    if (run.target) run.target.style.viewTransitionName = "";
    if (land && run.card.isConnected) {
      run.card
        .querySelector(".shot-stage")
        ?.scrollIntoView({ block: "center", behavior: "instant" });
      run.card.tabIndex = -1;
      run.card.focus({ preventScroll: true });
    }
    if (this.active === run) this.active = null;
    this.notify(run, "finish", {
      outcome,
      elapsed_ms: run.started ? performance.now() - run.started : 0,
    });
  }
  buildStage(run, interior, aerial, actual) {
    const stage = el("section", null, "descent-stage");
    stage.setAttribute("aria-label", "Inside-out descent");
    stage.tabIndex = -1;
    run.stage = stage;
    const mapLayer = el("div", null, "descent-layer descent-map location-map");
    const aerialLayer = el("div", null, "descent-layer descent-aerial");
    const interiorLayer = el("div", null, "descent-layer descent-interior");
    const plane = el("div", null, "descent-aerial-plane");
    interior.alt = actual
      ? "Matterport scan of the top-ranked location"
      : "Synthetic fixture interior";
    interiorLayer.append(interior);
    let outline;
    if (aerial) {
      plane.style.setProperty(
        "--aerial-ratio",
        aerial.image.naturalWidth / aerial.image.naturalHeight,
      );
      aerial.image.alt = "Vexcel aerial evidence for the top-ranked location";
      plane.append(aerial.image);
      if (aerial.path) {
        const svg = document.createElementNS(SVG, "svg");
        svg.setAttribute(
          "viewBox",
          `0 0 ${aerial.metadata.width} ${aerial.metadata.height}`,
        );
        svg.setAttribute(
          "aria-label",
          "Estimated parking outline from supplied geometry",
        );
        outline = document.createElementNS(SVG, "path");
        outline.setAttribute("d", aerial.path);
        outline.setAttribute("pathLength", "1000");
        outline.setAttribute("class", "descent-parking");
        outline.setAttribute("fill-rule", "evenodd");
        outline.style.strokeDasharray = "1000";
        outline.style.strokeDashoffset = "1000";
        svg.append(outline);
        plane.append(svg);
      }
      aerialLayer.append(plane);
    }
    const header = el("div", null, "descent-header"),
      title = el("div");
    title.append(
      el("h2", "Inside and out"),
      el("p", run.pick.property.address, "descent-address"),
    );
    const skipButton = button(
      "Skip descent",
      () => this.cancel(),
      "descent-skip",
    );
    header.append(title, skipButton);
    const caption = el("div", null, "descent-caption");
    const source = el("p", "", "descent-source"),
      note = el("p", "", "descent-note");
    source.setAttribute("aria-live", "polite");
    caption.append(source, note);
    const label = (layer, explanation) => {
      source.textContent = layer;
      note.textContent = explanation;
    };
    stage.append(mapLayer, aerialLayer, interiorLayer, header, caption);
    run.inert = [...document.body.children]
      .filter((node) => node instanceof HTMLElement)
      .map((node) => [node, node.inert]);
    run.inert.forEach(([node]) => {
      node.inert = true;
    });
    document.body.append(stage);
    document.body.classList.add("descent-playing");
    skipButton.focus({ preventScroll: true });
    run.started = performance.now();
    return {
      stage,
      mapLayer,
      aerialLayer,
      interiorLayer,
      plane,
      outline,
      label,
    };
  }
  async present(run, interior, aerial, actual) {
    const { mapLayer, aerialLayer, interiorLayer, plane, outline, label } =
      this.buildStage(run, interior, aerial, actual);
    const signal = run.abort.signal;
    if (actual)
      run.borrowed = stageMap(this.mapHost, mapLayer, run.pick, {
        reducedMotion: run.reduced,
      });
    if (run.borrowed) {
      label("Property location", "Click or press any key to skip");
      this.notify(run, "map");
      await new Promise((resolve) => requestAnimationFrame(resolve));
      if (signal.aborted) return;
      if (!run.reduced) run.borrowed.fly();
      await wait(run.reduced ? 200 : 900, signal);
    }
    if (signal.aborted) return;
    if (aerial) {
      const parking =
        run.pick.logistics?.parking_status ||
        (run.pick.logistics?.estimated === true ? "estimated" : "unknown");
      label("Vexcel aerial", `Parking ${parking} · aerial view`);
      this.notify(run, "aerial", { geometry: aerial.kind });
      this.animate(run, aerialLayer, [{ opacity: 0 }, { opacity: 1 }], {
        duration: 200,
      });
      if (outline)
        this.animate(
          run,
          outline,
          [{ strokeDashoffset: "1000" }, { strokeDashoffset: "0" }],
          { duration: run.reduced ? 1 : 650, easing: "linear" },
        );
      else if (!run.reduced)
        this.animate(
          run,
          plane,
          [{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)" }],
          { duration: 650 },
        );
      await wait(run.reduced ? 200 : 700, signal);
    }
    if (signal.aborted) return;
    label(
      actual
        ? aerial && !run.reduced
          ? "Vexcel aerial → Matterport scan"
          : "Matterport scan"
        : "MOCK · Synthetic frame",
      actual
        ? "The real scan point · image heading alignment unverified"
        : "Fixture preview · no live aerial evidence",
    );
    this.notify(run, "interior");
    if (!run.reduced && actual) {
      if (aerial)
        this.animate(
          run,
          plane,
          [
            { transform: "scale(1)", filter: "blur(0px)" },
            { transform: "scale(2.4)", filter: "blur(7px)" },
          ],
          { duration: 650 },
        );
      this.animate(
        run,
        interior,
        [{ transform: "scale(1.12)" }, { transform: "scale(1)" }],
        { duration: 650 },
      );
    }
    this.animate(run, interiorLayer, [{ opacity: 0 }, { opacity: 1 }], {
      duration: run.reduced || !actual ? 200 : 470,
      delay: run.reduced || !actual ? 0 : 180,
    });
    await wait(run.reduced || !actual ? 200 : 650, signal);
    if (signal.aborted) return;
    if (actual)
      label(
        "Matterport scan",
        "The real scan point · image heading alignment unverified",
      );
    await this.land(run, interior, actual);
  }
  async land(run, interior, actual) {
    const { card, stage } = run;
    const signal = run.abort.signal;
    this.notify(run, "land");
    const target = card.querySelector(".shot-image");
    run.target = target;
    if (
      !run.reduced &&
      actual &&
      target &&
      typeof document.startViewTransition === "function"
    ) {
      interior.style.viewTransitionName = "descent-frame";
      document.documentElement.classList.add("descent-transition");
      run.transition = document.startViewTransition(() => {
        if (run.done) return;
        stage.remove();
        run.borrowed?.restore();
        document.body.classList.remove("descent-playing");
        run.inert.forEach(([node, value]) => {
          node.inert = value;
        });
        card
          .querySelector(".shot-stage")
          .scrollIntoView({ block: "center", behavior: "instant" });
        target.style.viewTransitionName = "descent-frame";
      });
      await run.transition.finished.catch(() => {});
    } else {
      this.animate(run, stage, [{ opacity: 1 }, { opacity: 0 }], {
        duration: 200,
      });
      await wait(200, signal);
    }
    if (!signal.aborted) this.complete(run, "complete");
  }
  async play(data) {
    this.cancel("superseded", false);
    const pick = data.picks?.[0],
      card = document.querySelector("#results .pick-card");
    if (
      !pick ||
      !card ||
      document.hidden ||
      document.querySelector("dialog[open]")
    )
      return;
    const run = {
      data,
      pick,
      card,
      abort: new AbortController(),
      animations: [],
      listeners: [],
      reduced: matchMedia("(prefers-reduced-motion: reduce)").matches,
    };
    this.active = run;
    const signal = run.abort.signal;
    const listen = (target, name, listener, options) => {
      target.addEventListener(name, listener, options);
      run.listeners.push(() =>
        target.removeEventListener(name, listener, options),
      );
    };
    const skip = (event) => {
      if (run.stage) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
      this.cancel("skipped", Boolean(run.stage));
    };
    listen(document, "keydown", skip, true);
    listen(document, "click", skip, true);
    listen(document, "visibilitychange", () => {
      if (document.hidden) this.cancel("hidden", false);
    });
    try {
      const actual = data.source_mode === "live";
      const aerialPromise = actual
        ? aerialAssets(pick, signal)
        : Promise.resolve(null);
      const [interior, aerial] = await Promise.all([
        loadImage(pick.shots?.[0]?.image_path, signal),
        Promise.race([aerialPromise, wait(1800, signal).then(() => null)]),
      ]);
      if (signal.aborted) return;
      if (
        !interior ||
        document.hidden ||
        document.querySelector("dialog[open]")
      ) {
        this.complete(run, "unavailable", false);
        return;
      }
      card
        .querySelector(".shot-viewer")
        ?.dispatchEvent(new Event("typecast:reset-frame"));
      await this.present(run, interior, aerial, actual);
    } catch {
      this.complete(run, "unavailable", false);
    }
  }
}
