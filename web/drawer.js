import { el, button, assetUrl, formatNumber } from "./utils.js";
import { createTour } from "./tour.js";

const SOURCES = {
  costar: "CoStar",
  matterport: "Matterport",
  vexcel: "Vexcel",
};
const STATUSES = ["measured", "estimated", "unknown"];
let currentDrawer,
  nextId = 0;
export const numberKnown = (value) =>
  typeof value === "number" && Number.isFinite(value);
export const evidenceStatus = (status) =>
  STATUSES.includes(status) ? status : "unknown";
export const quantity = (value, unit = "", decimals = 1) =>
  numberKnown(value) ? `${formatNumber(value, decimals)}${unit}` : "unknown";
export function availability(property = {}) {
  const state = property.availability_status;
  if (state === "available") return { status: "available", text: "Available" };
  if (state === "not_available")
    return { status: "not_available", text: "Not available" };
  if (state === "unknown")
    return { status: "unknown", text: "Availability unknown" };
  // The legacy boolean is not evidence; missing or null status is unknown (matches agent/pipeline.py).
  return { status: "unknown", text: "Availability unknown" };
}
export function fitStatus(pick = {}) {
  const fit = pick.shot_fit ?? {};
  if (![fit.have_depth_m, fit.ceiling_m, fit.needed_depth_m].every(numberKnown))
    return "unknown";
  // Only explicitly measured geometry may support fits/tight; estimated or unsupplied stays unknown.
  if (pick.shots?.[0]?.measure_on_site !== false) return "unknown";
  if (["fits", "tight", "unknown"].includes(fit.status)) return fit.status;
  return fit.fits === true ? "fits" : fit.fits === false ? "tight" : "unknown";
}
export function logisticsStatus(logistics = {}, field) {
  const explicit = logistics[`${field}_status`];
  if (STATUSES.includes(explicit)) return explicit;
  if (
    field === "parking" &&
    !numberKnown(logistics.truck_spaces) &&
    !numberKnown(logistics.car_spaces)
  )
    return "unknown";
  if (field === "walk" && !numberKnown(logistics.walk_m)) return "unknown";
  if (field === "noise" && !logistics.noise_flags?.length) return "unknown";
  return logistics.estimated === true ? "estimated" : "unknown";
}
export function allEvidence(pick = {}) {
  return [
    ...(Array.isArray(pick.evidence) ? pick.evidence : []),
    ...(Array.isArray(pick.logistics?.source_evidence)
      ? pick.logistics.source_evidence
      : []),
  ];
}
export function sourceStatuses(pick) {
  const evidence = allEvidence(pick);
  return Object.entries(SOURCES).map(([source, label]) => {
    const rows = evidence.filter((item) => item.source === source);
    const status =
      !rows.length ||
      rows.some((item) => evidenceStatus(item.status) === "unknown")
        ? "unknown"
        : rows.some((item) => item.status === "estimated")
          ? "estimated"
          : "measured";
    return { source, label, status, count: rows.length };
  });
}
export function statusTag(text, status, className = "") {
  return el(
    "span",
    text,
    `evidence-status status-${evidenceStatus(status)} ${className}`.trim(),
  );
}
function arrowIcon(direction) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute(
    "d",
    direction === "previous" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7",
  );
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.6");
  svg.append(path);
  return svg;
}
export function createShotViewer(
  shots = [],
  { address = "this location", initialIndex = 0, className = "" } = {},
) {
  const available = Array.isArray(shots) ? shots : [];
  let index = available.length
    ? Math.max(0, Math.min(initialIndex, available.length - 1))
    : 0;
  const figure = el("figure", undefined, `shot-viewer ${className}`.trim());
  const stage = el("div", undefined, "shot-stage");
  const image = el("img", undefined, "shot-image");
  image.loading = "lazy";
  image.decoding = "async";
  const fallback = el("div", undefined, "image-fallback");
  fallback.append(
    el("span", "Frame unavailable", "image-fallback-title"),
    el("span", "Source image could not be loaded. Evidence remains available."),
  );
  fallback.hidden = true;
  stage.append(image, fallback);
  const caption = el("figcaption", undefined, "shot-caption");
  const count = el("span", undefined, "frame-count");
  count.setAttribute("aria-live", "polite");
  const controls = el("div", undefined, "frame-controls");
  function update() {
    const shot = available[index];
    image.hidden = false;
    fallback.hidden = true;
    const src = shot?.image_path ? assetUrl(shot.image_path) : "";
    image.alt = `Interior frame ${index + 1} of ${available.length} at ${address}`;
    if (src) image.src = src;
    else {
      image.removeAttribute("src");
      image.hidden = true;
      fallback.hidden = false;
      fallback.firstChild.textContent = available.length
        ? "Frame unavailable"
        : "No interior frame";
    }
    count.textContent = available.length
      ? `Frame ${index + 1} of ${available.length}`
      : "No frame";
  }
  image.addEventListener("error", () => {
    image.hidden = true;
    fallback.hidden = false;
  });
  if (available.length > 1) {
    for (const [direction, change] of [
      ["previous", -1],
      ["next", 1],
    ]) {
      const control = button(
        "",
        () => {
          index = (index + change + available.length) % available.length;
          update();
        },
        "frame-arrow",
      );
      control.setAttribute(
        "aria-label",
        `${direction === "previous" ? "Previous" : "Next"} interior frame at ${address}`,
      );
      control.append(arrowIcon(direction));
      controls.append(control);
    }
  }
  caption.append(count, controls);
  figure.addEventListener("typecast:reset-frame", () => {
    index = 0;
    update();
  });
  figure.append(stage, caption);
  update();
  return { element: figure, getIndex: () => index };
}
function detailSection(title) {
  const section = el("section", undefined, "detail-section");
  section.append(el("h3", title));
  return section;
}
function factList(rows) {
  const list = el("dl", undefined, "detail-facts");
  for (const [label, text] of rows) {
    const row = el("div");
    row.append(el("dt", label), el("dd", text));
    list.append(row);
  }
  return list;
}
function addAerial(section, path, address) {
  if (!path) return;
  const figure = el("figure", undefined, "detail-aerial");
  const image = el("img");
  image.src = assetUrl(path);
  image.alt = `Aerial parking evidence for ${address}`;
  image.loading = "lazy";
  const fallback = el(
    "p",
    "Aerial image unavailable. Source notes and counts remain below.",
    "image-fallback aerial-fallback",
  );
  fallback.hidden = true;
  image.addEventListener("error", () => {
    image.hidden = true;
    fallback.hidden = false;
  });
  figure.append(image, fallback, el("figcaption", "Vexcel aerial evidence"));
  section.append(figure);
}

export function openEvidenceDrawer(
  pick,
  { config = {}, onDraft, initialShotIndex = 0 } = {},
) {
  currentDrawer?.close();
  const restoreFocus = document.activeElement;
  const property = pick.property ?? {},
    fit = pick.shot_fit ?? {},
    logistics = pick.logistics ?? {};
  const shots = Array.isArray(pick.shots) ? pick.shots : [];
  const dialog = el("dialog", undefined, "evidence-drawer");
  const titleId = `evidence-title-${++nextId}`;
  dialog.setAttribute("aria-labelledby", titleId);
  const header = el("header", undefined, "drawer-header");
  const heading = el("div");
  const title = el("h2", property.address || "Location evidence");
  title.id = titleId;
  heading.append(
    title,
    el(
      "p",
      [`Pick ${pick.rank ?? "—"}`, property.city, property.type]
        .filter(Boolean)
        .join(" · "),
      "detail-muted",
    ),
  );
  const close = button("Close", () => dialog.close(), "drawer-close");
  close.setAttribute("aria-label", "Close evidence");
  close.autofocus = true;
  header.append(heading, close);
  const body = el("div", undefined, "drawer-body");
  const viewer = createShotViewer(shots, {
    address: property.address,
    initialIndex: initialShotIndex,
    className: "detail-shot",
  });
  body.append(
    viewer.element,
    el("p", pick.reason || "No ranking reason was supplied.", "detail-reason"),
  );
  const listing = detailSection("Property & availability");
  listing.append(
    factList([
      ["Availability", availability(property).text],
      ["Property type", property.type || "unknown"],
      ["Year built", quantity(property.year_built, "", 0)],
      ["Listing area", quantity(property.size_sqft, " sq ft", 0)],
      [
        "Listing types",
        property.listing_types?.length
          ? property.listing_types.join(", ")
          : "unknown",
      ],
    ]),
  );
  if (property.availability_reason)
    listing.append(el("p", property.availability_reason, "detail-muted"));
  listing.append(
    el(
      "p",
      "Listing availability does not establish filming permission.",
      "detail-muted",
    ),
  );
  body.append(listing);
  const geometry = detailSection("Shot fit");
  const status = fitStatus(pick);
  geometry.append(
    el(
      "span",
      status === "unknown"
        ? "Fit unknown"
        : status === "fits"
          ? "Shot fits"
          : "Shot is tight",
      `fit-badge fit-${status}`,
    ),
  );
  geometry.append(
    factList([
      ["Depth needed", quantity(fit.needed_depth_m, " m", 2)],
      ["Depth available", quantity(fit.have_depth_m, " m", 2)],
      ["Ceiling", quantity(fit.ceiling_m, " m", 2)],
    ]),
    el("p", fit.note || "No fit explanation was supplied.", "detail-muted"),
  );
  for (const [index, shot] of shots.entries()) {
    const row = el("div", undefined, "shot-fact-row");
    row.append(
      el("h4", `Frame ${index + 1}`),
      factList([
        ["Room area", quantity(shot.room_area_m2, " m²")],
        ["Ceiling", quantity(shot.ceiling_m, " m")],
        ["Directional depth", quantity(shot.depth_m, " m")],
        [
          "On-site measurement",
          shot.measure_on_site === true
            ? "Required"
            : "No requirement supplied",
        ],
        [
          "Image heading",
          `${quantity(shot.heading_deg, "°")} · alignment unverified`,
        ],
      ]),
    );
    if (shot.reason) row.append(el("p", shot.reason));
    geometry.append(row);
  }
  body.append(geometry);
  const crew = detailSection("Parking & access");
  crew.append(
    statusTag(
      logisticsStatus(logistics, "parking"),
      logisticsStatus(logistics, "parking"),
    ),
  );
  addAerial(
    crew,
    logistics.aerial_image_path,
    property.address || "this location",
  );
  crew.append(
    factList([
      ["Truck spaces", quantity(logistics.truck_spaces, "", 0)],
      ["Crew car spaces", quantity(logistics.car_spaces, "", 0)],
      [
        "Walk to location",
        `${quantity(logistics.walk_m, " m")} · ${logisticsStatus(logistics, "walk")}`,
      ],
      ["Parking area", quantity(logistics.parking_area_m2, " m²")],
    ]),
  );
  for (const [flag, value] of Object.entries(property.parking_flags ?? {}))
    crew.append(
      el(
        "p",
        `${flag.replaceAll("_", " ")}: ${value === true ? "yes" : value === false ? "no" : "unknown"}`,
        "detail-muted",
      ),
    );
  for (const note of logistics.source_notes ?? [])
    crew.append(el("p", note, "detail-source-note"));
  body.append(crew);
  const noise = detailSection("Noise");
  const noiseStatus = logisticsStatus(logistics, "noise");
  noise.append(statusTag(noiseStatus, noiseStatus));
  const noiseFlags = logistics.noise_flags ?? [];
  if (noiseFlags.length) {
    const list = el("ul", undefined, "noise-flags");
    for (const flag of noiseFlags) list.append(el("li", flag));
    noise.append(list);
  } else
    noise.append(
      el(
        "p",
        noiseStatus === "unknown"
          ? "Noise conditions are unknown. No flags were supplied."
          : "No noise flags reported by the source.",
      ),
    );
  body.append(noise);
  const skeptic = detailSection("Skeptic review");
  for (const note of pick.skeptic_notes ?? [])
    skeptic.append(
      el(
        "p",
        note,
        `skeptic-note ${/^no objection\.?$/i.test(note.trim()) ? "skeptic-clear" : ""}`,
      ),
    );
  if (!pick.skeptic_notes?.length)
    skeptic.append(el("p", "No skeptic review was supplied.", "detail-muted"));
  body.append(skeptic);
  const evidence = detailSection("Every source claim");
  const lines = allEvidence(pick);
  for (const [source, label] of Object.entries(SOURCES)) {
    const group = el("div", undefined, "evidence-source-group");
    group.append(el("h4", label));
    const matching = lines.filter((line) => line.source === source);
    if (!matching.length)
      group.append(
        el("p", "No source claim supplied.", "detail-muted"),
        statusTag("unknown", "unknown"),
      );
    for (const line of matching) {
      const item = el("div", undefined, "evidence-line");
      item.append(
        statusTag(evidenceStatus(line.status), line.status),
        el("p", line.claim || "No claim text supplied."),
      );
      group.append(item);
    }
    evidence.append(group);
  }
  body.append(evidence);
  let tour;
  const tourHost = el("div", undefined, "drawer-tour-host");
  if (shots.length) {
    tour = createTour(shots[viewer.getIndex()], config);
    tourHost.append(tour.element);
    if (shots.length > 1) {
      const updateTour = button(
        "Use the currently shown frame for the tour",
        () => {
          tour?.destroy();
          tour = createTour(shots[viewer.getIndex()], config);
          tourHost.replaceChildren(tour.element, updateTour);
        },
        "tour-frame-update",
      );
      tourHost.append(updateTour);
    }
  } else if (property.model_id) {
    tour = createTour({ model_id: property.model_id }, config);
    tourHost.append(tour.element);
  }
  body.append(tourHost);
  const footer = el("footer", undefined, "drawer-footer");
  const draftStatus = el("p", "", "drawer-draft-status");
  draftStatus.setAttribute("role", "status");
  const draft = button(
    "Draft note",
    async () => {
      if (typeof onDraft !== "function") return;
      draft.disabled = true;
      draft.setAttribute("aria-busy", "true");
      draftStatus.textContent = "";
      try {
        const message = await onDraft(pick);
        if (typeof message === "string" && message.trim()) {
          draftStatus.textContent = message;
          draftStatus.dataset.state =
            message === "Saved as a local draft, not sent" ? "saved" : "error";
        }
      } catch {
        draftStatus.textContent = "Draft could not be saved. Try again.";
      } finally {
        draft.disabled = false;
        draft.removeAttribute("aria-busy");
      }
    },
    "draft-note",
  );
  draft.disabled = typeof onDraft !== "function";
  footer.append(
    el("p", "Create a local inquiry draft for review.", "detail-muted"),
    draft,
    draftStatus,
  );
  dialog.append(header, body, footer);
  let cleaned = false;
  function cleanup() {
    if (cleaned) return;
    cleaned = true;
    tour?.destroy();
    dialog.remove();
    if (currentDrawer === dialog) currentDrawer = undefined;
    if (restoreFocus?.isConnected) restoreFocus.focus({ preventScroll: true });
  }
  dialog.addEventListener("close", cleanup, { once: true });
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (
      event.clientX < box.left ||
      event.clientX > box.right ||
      event.clientY < box.top ||
      event.clientY > box.bottom
    )
      dialog.close();
  });
  document.body.append(dialog);
  currentDrawer = dialog;
  dialog.showModal();
  return dialog;
}
