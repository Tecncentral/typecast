import * as L from "./vendor/leaflet/leaflet-src.esm.js";

const mountedMaps = new WeakMap();
const stagedMaps = new WeakMap();
let mapSequence = 0;

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

function parkingOutline(pick) {
  const logistics = pick?.logistics || {};
  const status = parkingStatus(pick);
  const style = {
    color: "#edbd69",
    weight: 2,
    fillColor: "#edbd69",
    fillOpacity: 0.1,
    dashArray: status === "measured" ? undefined : "6 5",
  };
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
export function renderMap(host, picks = [], { onSelect } = {}) {
  if (!(host instanceof HTMLElement))
    throw new TypeError("renderMap requires an HTML host element.");
  destroyMap(host);
  const shortlist = Array.isArray(picks)
    ? picks.filter((pick) => pick?.property)
    : [];
  const validPicks = shortlist.filter((pick) => coordinates(pick));
  const instanceId = `location-map-${++mapSequence}`;
  let disposed = false;
  let map;
  let tiles;
  let tileTimeout;
  let resizeObserver;
  let selectedOutline;
  let initialFrame;
  let restoreStage = null;
  const markerByPick = new Map();
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
  actions.append(aerialToggle, retry);
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
  const legend = element(
    "p",
    "location-map__legend",
    "Amber pins · top three picks",
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
    tiles.on("tileerror", () => showFallback());
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

  function select(pick, notify = true) {
    if (disposed) return;
    for (const [button, candidate] of selectionButtons) {
      button.setAttribute("aria-pressed", String(candidate === pick));
    }
    if (map) {
      selectedOutline?.remove();
      selectedOutline = parkingOutline(pick);
      selectedOutline?.addTo(map);
      const marker = markerByPick.get(pick);
      if (marker) {
        map.panTo(marker.getLatLng(), { animate: false });
        marker.openPopup();
      }
    }
    const status = parkingStatus(pick);
    outlineLabel.textContent = selectedOutline
      ? `Parking outline · ${status}`
      : "Parking outline unavailable";
    if (notify && typeof onSelect === "function") onSelect(pick);
  }

  listen(aerialToggle, "click", () => showGallery(gallery.hidden));
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
    button.setAttribute(
      "aria-label",
      `Pick ${label}: ${address(pick)}${point ? "" : ". Location coordinates unavailable"}`,
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
      popup.append(
        element("strong", "", `Pick ${label}`),
        element("span", "", address(pick)),
      );
      marker.bindPopup(popup, { maxWidth: 280, minWidth: 160, autoPan: false });
      marker.on("click", () => select(pick));
      markerByPick.set(pick, marker);
    }
    const bounds = L.latLngBounds(validPicks.map(coordinates));
    map.fitBounds(bounds, { padding: [45, 45], maxZoom: 15, animate: false });
    const firstPick = shortlist[0];
    // Show the first outline without moving the overview away from the shortlist.
    selectedOutline = parkingOutline(firstPick);
    selectedOutline?.addTo(map);
    outlineLabel.textContent = selectedOutline
      ? `Parking outline · ${parkingStatus(firstPick)}`
      : "Parking outline unavailable";
    for (const [button, candidate] of selectionButtons)
      button.setAttribute("aria-pressed", String(candidate === firstPick));
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
    stopTiles();
    window.cancelAnimationFrame(initialFrame);
    resizeObserver?.disconnect();
    listeners.forEach((remove) => remove());
    map?.remove();
    section.remove();
    if (mountedMaps.get(host) === cleanup) mountedMaps.delete(host);
    stagedMaps.delete(host);
  }
  mountedMaps.set(host, cleanup);
  return cleanup;
}
