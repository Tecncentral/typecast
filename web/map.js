import * as L from "./vendor/leaflet/leaflet-src.esm.js";
import {
  parkingBar,
  parkingSummary,
  vehiclesOf,
  verdictText,
  demandText,
  lotText,
} from "./parking.js";

const mountedMaps = new WeakMap();
const stagedMaps = new WeakMap();
const focusers = new WeakMap();
let mapSequence = 0;
const finite = (value) => typeof value === "number" && Number.isFinite(value);

/** Fly the rendered map to one pick's parking lot (used by the change summary). */
export function focusMapPick(host, propertyId) {
  return focusers.get(host)?.(propertyId) || false;
}

// Borrow the actual map for the descent, then restore its DOM and overview.
export function stageMap(
  host,
  destination,
  pick,
  { duration = 900, reducedMotion = false } = {},
) {
  return (
    stagedMaps.get(host)?.(destination, pick, { duration, reducedMotion }) ||
    null
  );
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function validCoordinates(lat, lon) {
  return (
    typeof lat === "number" &&
    typeof lon === "number" &&
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    Math.abs(lat) <= 90 &&
    Math.abs(lon) <= 180
  );
}

function coordinates(pick) {
  const { lat, lon } = pick?.property || {};
  return validCoordinates(lat, lon) ? [lat, lon] : null;
}

function rankLabel(pick) {
  return Number.isInteger(pick.rank) && pick.rank > 0 ? String(pick.rank) : "—";
}

function address(pick) {
  return (
    pick?.property?.address || pick?.property?.city || "Address unavailable"
  );
}

function localAerialPath(path) {
  if (typeof path !== "string") return null;
  const local = path.replace(/^\.\//, "").replace(/^\/+/, "");
  if (
    !/^(cache|mocks)\//.test(local) ||
    /[\\?#]/.test(local) ||
    local.split("/").some((part) => part === "..")
  )
    return null;
  return `/${local}`;
}

function parkingStatus(pick) {
  const status = pick?.logistics?.parking_status;
  if (["measured", "estimated", "unknown"].includes(status)) return status;
  return pick?.logistics?.estimated === true ? "estimated" : "unknown";
}

function validRing(ring, geoJSON = false) {
  return (
    Array.isArray(ring) &&
    ring.length >= 3 &&
    ring.every(
      (point) =>
        Array.isArray(point) &&
        point.length >= 2 &&
        (geoJSON
          ? validCoordinates(point[1], point[0])
          : validCoordinates(point[0], point[1])),
    )
  );
}

const FIT_COLOURS = { fits: "#edbd69", short: "#ff5f57", unknown: "#adb5b3" };

function lotStyle(summary, selected) {
  const tone =
    summary.fits === true ? "fits" : summary.fits === false ? "short" : "unknown";
  return {
    color: FIT_COLOURS[tone],
    weight: selected ? 3 : 2,
    opacity: 1,
    fillColor: FIT_COLOURS[tone],
    fillOpacity: selected ? 0.32 : 0.2,
    dashArray: summary.status === "measured" ? undefined : "6 5",
    smoothFactor: 1.5,
  };
}

/**
 * A standalone label above the lot. A polygon's own tooltip anchors at a centre
 * computed at the zoom it was added, where a lot is a pixel wide, so it drifts
 * hundreds of pixels once you zoom in. Bounds are zoom-independent.
 */
function lotLabel(lot, content, className) {
  const bounds = lot.getBounds();
  return L.tooltip({
    permanent: true,
    direction: "top",
    className,
    opacity: 1,
    interactive: false,
  })
    .setLatLng(L.latLng(bounds.getNorth(), bounds.getCenter().lng))
    .setContent(content);
}

/** Validated georeferencing for the cached, unannotated Vexcel aerial. */
async function aerialOverlay(pick, signal) {
  const id = pick?.property?.property_id;
  if (!/^[0-9]{1,12}$/.test(id || "")) return null;
  try {
    const response = await fetch(`/api/aerial/${encodeURIComponent(id)}`, {
      signal,
      cache: "no-store",
    });
    if (!response.ok) return null;
    const metadata = await response.json();
    const { extent, coordinates } = metadata;
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
      Math.abs(coordinates[0] - pick.property.lat) > 1e-6 ||
      Math.abs(coordinates[1] - pick.property.lon) > 1e-6
    )
      return null;
    // The extract is north-up Web Mercator, the same projection as the map.
    const southWest = L.Projection.SphericalMercator.unproject(
      L.point(extent[0], extent[1]),
    );
    const northEast = L.Projection.SphericalMercator.unproject(
      L.point(extent[2], extent[3]),
    );
    return {
      src: `/${metadata.image_path}`,
      bounds: L.latLngBounds(southWest, northEast),
    };
  } catch {
    return null;
  }
}

function parkingOutline(pick, style) {
  const logistics = pick?.logistics || {};
  const geometry = logistics.parking_geometry;
  // L.geoJSON converts GeoJSON [longitude, latitude] into Leaflet [latitude, longitude].
  if (
    geometry?.type === "Polygon" &&
    Array.isArray(geometry.coordinates) &&
    geometry.coordinates.length &&
    geometry.coordinates.every((ring) => validRing(ring, true))
  ) {
    return L.geoJSON(geometry, { style });
  }
  if (
    geometry?.type === "MultiPolygon" &&
    Array.isArray(geometry.coordinates) &&
    geometry.coordinates.length &&
    geometry.coordinates.every(
      (polygon) =>
        Array.isArray(polygon) &&
        polygon.length &&
        polygon.every((ring) => validRing(ring, true)),
    )
  ) {
    return L.geoJSON(geometry, { style });
  }
  // The legacy contract is already [latitude, longitude]; do not reverse it.
  if (validRing(logistics.parking_polygon))
    return L.polygon(logistics.parking_polygon, style);
  return null;
}

/** Remove a previously rendered map, including observers, tile requests and listeners. */
export function destroyMap(host) {
  mountedMaps.get(host)?.();
}

/**
 * Render actual property coordinates and local aerial evidence.
 * Leaflet assets are local; only the optional OpenStreetMap basemap uses the network.
 * @returns {Function} an idempotent cleanup function
 */
export function renderMap(
  host,
  picks = [],
  { onSelect, vehicles, previous } = {},
) {
  if (!(host instanceof HTMLElement))
    throw new TypeError("renderMap requires an HTML host element.");
  destroyMap(host);
  const shortlist = Array.isArray(picks)
    ? picks.filter((pick) => pick?.property)
    : [];
  const validPicks = shortlist.filter((pick) => coordinates(pick));
  const demand = vehicles || vehiclesOf({ picks: shortlist });
  const earlier = previous?.picks?.length ? previous : null;
  const earlierDemand = earlier ? vehiclesOf(earlier) : null;
  const earlierById = new Map(
    (earlier?.picks || []).map((pick) => [pick.property?.property_id, pick]),
  );
  const currentIds = new Set(shortlist.map((pick) => pick.property.property_id));
  const dropped = (earlier?.picks || []).filter(
    (pick) =>
      pick?.property && !currentIds.has(pick.property.property_id) && coordinates(pick),
  );
  const summaries = new Map(
    shortlist.map((pick) => [pick, parkingSummary(pick, demand)]),
  );
  const vehiclesChanged =
    earlierDemand &&
    (earlierDemand.trucks !== demand.trucks || earlierDemand.cars !== demand.cars);
  const aborter = new AbortController();
  const instanceId = `location-map-${++mapSequence}`;
  let disposed = false;
  let map;
  let tiles;
  let tileTimeout;
  let resizeObserver;
  let selectedOutline;
  let initialFrame;
  let restoreStage = null;
  let overview;
  let selectedPick = null;
  const markerByPick = new Map();
  const lotByPick = new Map();
  const ghostByPick = new Map();
  const aerialBoundsByPick = new Map();
  let lotGroup;
  let ghostGroup;
  const selectionButtons = [];
  const listeners = [];

  function listen(target, type, callback) {
    target.addEventListener(type, callback);
    listeners.push(() => target.removeEventListener(type, callback));
  }

  const section = element("section", "location-map");
  section.setAttribute("aria-labelledby", `${instanceId}-title`);
  const header = element("div", "location-map__header");
  const heading = element("div");
  const title = element("h3", "location-map__title", "Shortlist on the ground");
  title.id = `${instanceId}-title`;
  heading.append(title);
  const subtitle = element(
    "p",
    "location-map__subtitle",
    demand.trucks === null
      ? "Vexcel aerials and segmented parking lots at each pick's coordinates."
      : `Parking for ${demandText(demand)}, checked against the nearest lot traced on each Vexcel aerial. Access and permission are unverified.`,
  );
  heading.append(subtitle);
  if (vehiclesChanged && earlierDemand.trucks !== null) {
    const chip = element(
      "p",
      "location-map__change",
      `Crew vehicles ${demandText(earlierDemand)} → ${demandText(demand)}`,
    );
    heading.append(chip);
  }
  const actions = element("div", "location-map__actions");
  const aerialToggle = element(
    "button",
    "location-map__action",
    "View aerials",
  );
  aerialToggle.type = "button";
  aerialToggle.setAttribute("aria-expanded", "false");
  aerialToggle.setAttribute("aria-controls", `${instanceId}-aerials`);
  const retry = element("button", "location-map__action", "Retry street map");
  retry.type = "button";
  retry.hidden = true;
  const overviewButton = element(
    "button",
    "location-map__action",
    "Show all picks",
  );
  overviewButton.type = "button";
  overviewButton.hidden = true;
  actions.append(overviewButton, aerialToggle, retry);
  header.append(heading, actions);
  const status = element("p", "location-map__status", "Loading street map…");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const canvas = element("div", "location-map__canvas");
  canvas.setAttribute("role", "region");
  canvas.setAttribute(
    "aria-label",
    "Property locations. Use arrow keys to pan and plus or minus to zoom.",
  );
  const legend = element("p", "location-map__legend");
  legend.append(
    element("span", "location-map__key location-map__key--pin", "Top three picks"),
    element("span", "location-map__key location-map__key--fits", "Lot fits the crew"),
    element("span", "location-map__key location-map__key--short", "Lot too small"),
    element("span", "location-map__key location-map__key--aerial", "Vexcel aerial"),
  );
  if (dropped.length)
    legend.append(
      element("span", "location-map__key location-map__key--ghost", "Left the shortlist"),
    );
  const outlineLabel = element("span", "location-map__outline-label");
  legend.append(outlineLabel);
  const locations = element("ul", "location-map__locations");
  locations.setAttribute("aria-label", "Select a property");
  const gallery = element("div", "location-map__aerials");
  gallery.id = `${instanceId}-aerials`;
  gallery.hidden = true;
  gallery.setAttribute("aria-label", "Local aerial evidence");
  section.append(header, status, canvas, legend, locations, gallery);
  host.replaceChildren(section);

  function showGallery(show) {
    gallery.hidden = !show;
    aerialToggle.setAttribute("aria-expanded", String(show));
    aerialToggle.textContent = show ? "Hide aerials" : "View aerials";
  }

  function stopTiles() {
    window.clearTimeout(tileTimeout);
    if (tiles) {
      tiles.off();
      tiles.remove();
      tiles = undefined;
    }
  }

  function showFallback(
    message = "Street map unavailable. Pins retain supplied coordinates; local aerial evidence is shown below.",
  ) {
    if (disposed) return;
    stopTiles();
    section.classList.add("location-map--offline");
    status.textContent = message;
    retry.hidden = !map;
    showGallery(true);
  }

  function loadTiles() {
    if (!map || disposed) return;
    stopTiles();
    if (navigator.onLine === false) {
      showFallback();
      return;
    }
    section.classList.remove("location-map--offline");
    retry.hidden = true;
    status.textContent = "Loading street map…";
    tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      keepBuffer: 1,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    });
    // Venue Wi-Fi drops the odd tile; give up only when nothing has loaded.
    let tileErrors = 0,
      tileLoaded = false;
    tiles.on("tileload", () => (tileLoaded = true));
    tiles.on("tileerror", () => {
      if (++tileErrors >= 8 && !tileLoaded) showFallback();
    });
    tiles.on("load", () => {
      window.clearTimeout(tileTimeout);
      if (tiles && !disposed)
        status.textContent =
          "Pins use supplied property coordinates. Select a pin to inspect the pick.";
    });
    tileTimeout = window.setTimeout(
      () =>
        showFallback(
          "Street map is taking too long to load. Pins retain supplied coordinates; local aerial evidence is shown below.",
        ),
      7000,
    );
    tiles.addTo(map);
  }

  function highlight(pick) {
    selectedPick = pick;
    for (const [button, candidate] of selectionButtons) {
      button.setAttribute("aria-pressed", String(candidate === pick));
    }
    for (const [candidate, layer] of lotByPick) {
      layer.setStyle(lotStyle(summaries.get(candidate), candidate === pick));
      if (candidate === pick) layer.bringToFront();
    }
    selectedOutline = lotByPick.get(pick) || null;
    outlineLabel.textContent = selectedOutline
      ? `Pick ${rankLabel(pick)} lot · ${parkingStatus(pick)}, access unverified`
      : `Pick ${rankLabel(pick)} · parking outline unavailable`;
  }

  // Zoom to the lot and its aerial; fall back to the pin.
  function frame(pick, animate = true) {
    const marker = markerByPick.get(pick) || ghostByPick.get(pick)?.marker;
    if (!map || !marker) return;
    const target = L.latLngBounds([marker.getLatLng()]);
    const lot = lotByPick.get(pick) || ghostByPick.get(pick)?.lot;
    if (lot) target.extend(lot.getBounds());
    const aerial = aerialBoundsByPick.get(pick);
    if (aerial && !lot) target.extend(aerial);
    map.flyToBounds(target.pad(0.35), {
      maxZoom: 18,
      duration: 0.9,
      animate: animate && !matchMedia("(prefers-reduced-motion: reduce)").matches,
    });
    overviewButton.hidden = false;
  }

  // Selecting stays on the map; the pin's popup links to the card.
  function select(pick) {
    if (disposed) return;
    highlight(pick);
    map?.closePopup();
    frame(pick);
  }

  listen(aerialToggle, "click", () => showGallery(gallery.hidden));
  listen(overviewButton, "click", () => {
    if (!map || !overview) return;
    map.flyToBounds(overview, {
      padding: [45, 45],
      maxZoom: 15,
      duration: 0.9,
      animate: !matchMedia("(prefers-reduced-motion: reduce)").matches,
    });
    overviewButton.hidden = true;
  });
  listen(retry, "click", loadTiles);
  listen(window, "offline", () => showFallback());

  for (const pick of shortlist) {
    const label = rankLabel(pick);
    const point = coordinates(pick);
    const item = element("li");
    const button = element("button", "location-map__location");
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    const rank = element("span", "location-map__rank", label);
    rank.setAttribute("aria-hidden", "true");
    const description = element("span", "location-map__location-text");
    description.append(element("span", "location-map__address", address(pick)));
    description.append(
      element(
        "span",
        "location-map__coordinates",
        point
          ? `${point[0].toFixed(4)}, ${point[1].toFixed(4)}`
          : "Location coordinates unavailable",
      ),
    );
    button.append(rank, description);
    const summary = summaries.get(pick);
    const before = earlierById.get(pick.property.property_id);
    description.append(
      parkingBar(summary, {
        compact: true,
        previous: before ? parkingSummary(before, earlierDemand) : undefined,
      }),
    );
    button.setAttribute(
      "aria-label",
      `Pick ${label}: ${address(pick)}. ${verdictText(summary)}.${point ? "" : " Location coordinates unavailable"}`,
    );
    selectionButtons.push([button, pick]);
    listen(button, "click", () => select(pick));
    item.append(button);
    locations.append(item);

    const aerialButton = element("button", "location-map__aerial");
    aerialButton.type = "button";
    aerialButton.setAttribute(
      "aria-label",
      `Inspect pick ${label}: ${address(pick)}`,
    );
    aerialButton.setAttribute("aria-pressed", "false");
    selectionButtons.push([aerialButton, pick]);
    const media = element("span", "location-map__aerial-media");
    const imagePath = localAerialPath(pick.logistics?.aerial_image_path);
    const unavailable = () =>
      media.replaceChildren(
        element(
          "span",
          "location-map__image-unavailable",
          "Aerial image unavailable",
        ),
      );
    if (imagePath) {
      const image = element("img", "location-map__aerial-image");
      image.alt = `Aerial evidence for ${address(pick)}`;
      image.loading = "lazy";
      image.decoding = "async";
      listen(image, "error", unavailable);
      image.src = imagePath;
      media.append(image);
    } else unavailable();
    const caption = element("span", "location-map__aerial-caption");
    caption.append(
      element(
        "span",
        "location-map__aerial-title",
        `${label} / ${address(pick)}`,
      ),
    );
    caption.append(
      element(
        "span",
        "location-map__aerial-status",
        imagePath
          ? `Vexcel aerial · parking ${parkingStatus(pick)}`
          : "No local aerial supplied for this pick",
      ),
    );
    aerialButton.append(media, caption);
    listen(aerialButton, "click", () => select(pick));
    gallery.append(aerialButton);
  }

  if (validPicks.length) {
    map = L.map(canvas, {
      center: coordinates(validPicks[0]),
      zoom: 14,
      minZoom: 2,
      maxZoom: 19,
      scrollWheelZoom: false,
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
    });
    map.attributionControl.setPrefix(
      '<a href="https://leafletjs.com" target="_blank" rel="noopener noreferrer">Leaflet</a>',
    );
    map.attributionControl.addAttribution("Aerials © Vexcel");
    // Aerials sit above the street tiles and below the lot outlines.
    map.createPane("aerials").style.zIndex = "350";
    const syncLabels = () =>
      section.classList.toggle("location-map--near", map.getZoom() >= 16);
    map.on("zoomend", syncLabels);
    lotGroup = L.featureGroup().addTo(map);
    for (const pick of validPicks) {
      const summary = summaries.get(pick);
      const lot = parkingOutline(pick, lotStyle(summary, false));
      if (!lot) continue;
      const label = element("span", "location-map__lot-text");
      label.append(
        element("strong", "", `${rankLabel(pick)} · ${verdictText(summary)}`),
        element("span", "", lotText(summary)),
      );
      if (summary.recorded) label.append(element("span", "", summary.recorded));
      lotLabel(lot, label, "location-map__lot-label").addTo(lotGroup);
      lot.on("click", () => select(pick));
      lot.addTo(lotGroup);
      lotByPick.set(pick, lot);
    }
    ghostGroup = L.layerGroup().addTo(map);
    for (const pick of dropped) {
      // Judge the dropped pick against the new demand, from its earlier payload.
      const summary = parkingSummary(pick, demand);
      const short = summary.fits === false;
      const why = short
        ? `${verdictText(summary)} for ${demandText(demand)}`
        : "left the shortlist on re-ranking";
      const ghost = L.marker(coordinates(pick), {
        icon: L.divIcon({
          className: `location-map__pin location-map__pin--ghost${short ? " location-map__pin--short" : ""}`,
          html: '<span aria-hidden="true">×</span>',
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        }),
        keyboard: false,
        interactive: true,
        title: `${address(pick)}: ${why}`,
        alt: `${address(pick)}: ${why}`,
      });
      ghost.bindTooltip(`${address(pick)} · ${why}`, {
        direction: "top",
        className: "location-map__ghost-label",
      });
      ghost.addTo(ghostGroup);
      ghostByPick.set(pick, { marker: ghost });
      const lot = parkingOutline(pick, {
        ...lotStyle(summary, false),
        fillOpacity: short ? 0.28 : 0.08,
      });
      if (!lot) continue;
      const label = element("span", "location-map__lot-text");
      label.append(
        element("strong", "", `Left · ${short ? verdictText(summary) : address(pick)}`),
        element("span", "", lotText(summary)),
      );
      lotLabel(
        lot,
        label,
        `location-map__lot-label${short ? " location-map__lot-label--short" : ""}`,
      ).addTo(ghostGroup);
      lot.addTo(ghostGroup);
      ghostByPick.get(pick).lot = lot;
    }
    for (const pick of [...validPicks, ...dropped]) {
      aerialOverlay(pick, aborter.signal).then((overlay) => {
        if (!overlay || disposed || !map) return;
        aerialBoundsByPick.set(pick, overlay.bounds);
        L.imageOverlay(overlay.src, overlay.bounds, {
          pane: "aerials",
          interactive: false,
          className: "location-map__aerial-overlay",
          alt: `Vexcel aerial around ${address(pick)}`,
        }).addTo(map);
      });
    }
    for (const pick of validPicks) {
      const label = rankLabel(pick);
      const top = pick.rank >= 1 && pick.rank <= 3;
      const icon = L.divIcon({
        className: `location-map__pin${top ? " location-map__pin--top" : ""}`,
        html: `<span aria-hidden="true">${label}</span>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20],
        popupAnchor: [0, -22],
      });
      const marker = L.marker(coordinates(pick), {
        icon,
        keyboard: true,
        title: `Pick ${label}: ${address(pick)}`,
        alt: `Pick ${label}: ${address(pick)}`,
        riseOnHover: true,
        zIndexOffset: top ? 100 - pick.rank : 0,
      }).addTo(map);
      const markerElement = marker.getElement();
      markerElement?.setAttribute(
        "aria-label",
        `Pick ${label}: ${address(pick)}`,
      );
      if (markerElement)
        listen(markerElement, "keydown", (event) => {
          if (event.key === " ") {
            event.preventDefault();
            select(pick);
          }
        });
      const popup = element("div", "location-map__popup");
      const toCard = element("button", "location-map__popup-action", "Go to card");
      toCard.type = "button";
      listen(toCard, "click", () => {
        map?.closePopup();
        if (typeof onSelect === "function") onSelect(pick);
      });
      popup.append(
        element("strong", "", `Pick ${label}`),
        element("span", "", address(pick)),
        element("span", "location-map__popup-verdict", verdictText(summaries.get(pick))),
        toCard,
      );
      marker.bindPopup(popup, { maxWidth: 280, minWidth: 160, autoPan: false });
      marker.on("click", () => select(pick));
      markerByPick.set(pick, marker);
    }
    const bounds = L.latLngBounds(validPicks.map(coordinates));
    overview = L.latLngBounds([
      ...validPicks.map(coordinates),
      ...dropped.map(coordinates),
    ]);
    map.fitBounds(overview, { padding: [45, 45], maxZoom: 15, animate: false });
    syncLabels();
    // Highlight the first lot without moving the overview away from the shortlist.
    highlight(shortlist[0]);
    focusers.set(host, (propertyId) => {
      const pick = [...shortlist, ...dropped].find(
        (candidate) => candidate.property.property_id === propertyId,
      );
      if (!pick || disposed) return false;
      if (markerByPick.has(pick)) highlight(pick);
      // Let the scroll settle before flying, so the motion is visible.
      window.setTimeout(() => !disposed && frame(pick), 450);
      return true;
    });
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        if (!disposed) map.invalidateSize({ pan: false });
      });
      resizeObserver.observe(canvas);
    }
    initialFrame = window.requestAnimationFrame(() => {
      if (!disposed) map.invalidateSize({ pan: false });
    });
    loadTiles();
    stagedMaps.set(host, (destination, pick, options) => {
      const point = coordinates(pick);
      if (disposed || !point || !map) return null;
      restoreStage?.();
      const center = map.getCenter(),
        zoom = map.getZoom();
      const sibling = canvas.nextSibling;
      map.closePopup();
      // The descent reveals its own aerial; keep the map phase a street map.
      map.getPane("aerials").style.display = "none";
      lotGroup?.remove();
      ghostGroup?.remove();
      destination.append(canvas);
      map.invalidateSize({ pan: false });
      map.fitBounds(bounds, { padding: [75, 75], maxZoom: 15, animate: false });
      for (const [candidate, marker] of markerByPick)
        marker.setOpacity(
          candidate.property.property_id === pick.property.property_id
            ? 1
            : 0.24,
        );
      let restored = false;
      restoreStage = () => {
        if (restored) return;
        restored = true;
        map.stop();
        if (sibling?.parentNode === section)
          section.insertBefore(canvas, sibling);
        else section.append(canvas);
        for (const marker of markerByPick.values()) marker.setOpacity(1);
        map.getPane("aerials").style.display = "";
        lotGroup?.addTo(map);
        ghostGroup?.addTo(map);
        if (selectedPick) highlight(selectedPick);
        map.invalidateSize({ pan: false });
        map.setView(center, zoom, { animate: false });
        restoreStage = null;
      };
      return {
        fly() {
          if (restored || disposed) return;
          map.flyTo(point, Math.max(17, Math.min(19, zoom + 3)), {
            duration: options.duration / 1000,
            animate: !options.reducedMotion,
          });
        },
        restore: restoreStage,
      };
    });
  } else {
    canvas.hidden = true;
    legend.hidden = true;
    aerialToggle.hidden = shortlist.length === 0;
    if (shortlist.length) {
      showFallback(
        "No property coordinates supplied. Inspect the local aerial evidence below.",
      );
    } else {
      status.textContent = "Location map appears when the scout returns picks.";
      aerialToggle.hidden = true;
      locations.hidden = true;
    }
  }

  function cleanup() {
    if (disposed) return;
    restoreStage?.();
    disposed = true;
    aborter.abort();
    stopTiles();
    window.cancelAnimationFrame(initialFrame);
    resizeObserver?.disconnect();
    listeners.forEach((remove) => remove());
    map?.remove();
    section.remove();
    if (mountedMaps.get(host) === cleanup) mountedMaps.delete(host);
    stagedMaps.delete(host);
    focusers.delete(host);
  }
  mountedMaps.set(host, cleanup);
  return cleanup;
}
