// Parking demand against the nearby lot traced on the Vexcel aerial, using the
// backend rule (data/vexcel_tools.py): capacity = floor(area / 30 m²) car
// equivalents, one truck consumes four. Every figure is an estimate; the lot
// is the nearest candidate, not confirmed as the property's own parking.

export const M2_PER_CAR = 30;
export const CARS_PER_TRUCK = 4;

const count = (value) =>
  Number.isInteger(value) && value >= 0 ? value : null;
const area = (value) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : null;

/** Requested crew vehicles: the response's own record, else the truck allocation. */
export function vehiclesOf(response) {
  const trucks = count(response?.vehicles?.trucks);
  const cars = count(response?.vehicles?.cars);
  if (trucks !== null && cars !== null) return { trucks, cars, known: true };
  const allocated = (response?.picks || [])
    .map((pick) => count(pick?.logistics?.truck_spaces))
    .filter((value) => value !== null);
  return {
    trucks: allocated.length ? Math.max(...allocated) : null,
    cars: null,
    known: false,
  };
}

/** Who drew the lot outline, read from the logistics evidence. */
export function lotSource(pick) {
  for (const item of pick?.logistics?.source_evidence || []) {
    const claim = String(item?.claim || "");
    if (claim.startsWith("Vexcel SAM3")) return "Vexcel-segmented";
    if (claim.startsWith("OSM mapped")) return "OSM-mapped";
  }
  return null;
}

/** CoStar's recorded spaces by type, e.g. [["Surface", 73], ["Covered", 129]]. */
export function recordedSpaces(pick) {
  const spaces = pick?.property?.parking_spaces;
  if (!spaces || typeof spaces !== "object") return [];
  return Object.entries(spaces).filter(
    ([type, value]) => typeof type === "string" && Number.isInteger(value) && value >= 0,
  );
}

export function recordedText(pick) {
  const spaces = recordedSpaces(pick);
  if (!spaces.length) return null;
  return (
    "CoStar record: " +
    spaces
      .map(([type, value]) => `${value.toLocaleString("en-US")} ${type.toLowerCase()}`)
      .join(" + ") +
    " spaces"
  );
}

/**
 * Capacity, demand and fit for one pick. `fits` is null whenever the lot or
 * the demand is unknown; nothing here claims a measured layout.
 */
export function parkingSummary(pick, vehicles) {
  const logistics = pick?.logistics || {};
  // A sliver under one car space is a segmentation artefact, not a lot.
  const traced =
    logistics.parking_status === "unknown" ? null : area(logistics.parking_area_m2);
  const lotArea = traced !== null && traced >= M2_PER_CAR ? traced : null;
  const capacity =
    lotArea === null ? null : Math.floor(lotArea / M2_PER_CAR);
  const trucks = count(vehicles?.trucks) ?? count(logistics.truck_spaces);
  const cars = count(vehicles?.cars);
  const truckLoad = trucks === null ? null : trucks * CARS_PER_TRUCK;
  const demand = truckLoad === null ? null : truckLoad + (cars ?? 0);
  const none = trucks === 0 && (cars ?? 0) === 0;
  let fits = null;
  if (capacity !== null && demand !== null && !none) {
    if (demand > capacity) fits = false;
    // Trucks alone fitting says nothing about the crew cars still unknown.
    else if (cars !== null) fits = true;
  }
  return {
    status: lotArea === null ? "unknown" : logistics.parking_status || "estimated",
    area: lotArea,
    capacity,
    trucks,
    cars,
    truckLoad,
    demand,
    spare: capacity === null || demand === null ? null : capacity - demand,
    fits,
    none,
    source: lotSource(pick),
    recorded: recordedText(pick),
  };
}

const fmt = (value) =>
  typeof value === "number" && Number.isFinite(value)
    ? Math.round(value).toLocaleString("en-US")
    : "unknown";

export function plural(value, word) {
  return `${fmt(value)} ${word}${value === 1 ? "" : "s"}`;
}

/** "5 trucks + 10 cars" — what the crew asked for. */
export function demandText(summary) {
  if (summary.trucks === null) return "Crew vehicles unknown";
  return summary.cars === null
    ? plural(summary.trucks, "truck")
    : `${plural(summary.trucks, "truck")} + ${plural(summary.cars, "car")}`;
}

/** Short verdict for labels and pins. The lot is nearby, not confirmed as the property's. */
export function verdictText(summary) {
  if (summary.capacity === null) return "Nearby lot size unknown";
  if (summary.none) return "No crew vehicles requested";
  if (summary.fits === true) return `Lot covers ${demandText(summary)}`;
  if (summary.fits === false)
    return `Lot short by ${plural(summary.demand - summary.capacity, "car space")}`;
  return `${demandText(summary)} · fit unconfirmed`;
}

/** "Nearby Vexcel-segmented lot ≈2,714 m² · ≈90 car spaces (est.)" */
export function lotText(summary) {
  if (summary.capacity === null) return "No usable lot outline";
  return `Nearby ${summary.source ? summary.source + " " : ""}lot ≈${fmt(
    summary.area,
  )} m² · ≈${plural(summary.capacity, "car space")} (est.)`;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function segmentShares(summary) {
  // Scale against whichever is larger, so an overflow is drawn past the lot.
  const scale = Math.max(summary.capacity ?? 0, summary.demand ?? 0, 1);
  const truck = (summary.truckLoad ?? 0) / scale;
  const cars = (summary.cars ?? 0) / scale;
  const lot = (summary.capacity ?? 0) / scale;
  return { truck, cars, lot };
}

function applyShares(bar, shares) {
  bar.style.setProperty("--truck", String(shares.truck));
  bar.style.setProperty("--cars", String(shares.cars));
  bar.style.setProperty("--lot", String(shares.lot));
}

/**
 * Demand-vs-capacity bar. With `previous`, it renders the earlier allocation
 * first and animates to the new one on the next frame.
 */
export function parkingBar(summary, { previous, compact = false } = {}) {
  const wrap = element(
    "div",
    `parking-bar${compact ? " parking-bar--compact" : ""}${
      summary.fits === false ? " parking-bar--short" : ""
    }${summary.capacity === null ? " parking-bar--unknown" : ""}`,
  );
  const head = element("div", "parking-bar__head");
  head.append(
    element(
      "span",
      `parking-bar__verdict parking-bar__verdict--${
        summary.fits === true ? "fits" : summary.fits === false ? "short" : "unknown"
      }`,
      verdictText(summary),
    ),
    element("span", "parking-bar__capacity", lotText(summary)),
  );
  const bar = element("div", "parking-bar__track");
  bar.setAttribute("role", "img");
  bar.setAttribute(
    "aria-label",
    summary.capacity === null
      ? "Parking capacity unknown."
      : `${demandText(summary)} use ${fmt(summary.demand)} of about ${fmt(
          summary.capacity,
        )} car spaces in the estimated lot.`,
  );
  const lot = element("span", "parking-bar__lot");
  const trucks = element("span", "parking-bar__seg parking-bar__seg--trucks");
  const cars = element("span", "parking-bar__seg parking-bar__seg--cars");
  bar.append(lot, trucks, cars);
  const key = element("div", "parking-bar__key");
  if (summary.trucks !== null)
    key.append(
      element(
        "span",
        "parking-bar__key-item parking-bar__key-item--trucks",
        `${plural(summary.trucks, "truck")} = ${fmt(summary.truckLoad)}`,
      ),
    );
  if (summary.cars !== null)
    key.append(
      element(
        "span",
        "parking-bar__key-item parking-bar__key-item--cars",
        `${plural(summary.cars, "crew car")}`,
      ),
    );
  if (summary.spare !== null)
    key.append(
      element(
        "span",
        "parking-bar__key-item parking-bar__key-item--spare",
        summary.spare >= 0
          ? `${fmt(summary.spare)} spare`
          : `${fmt(-summary.spare)} over`,
      ),
    );
  if (previous && previous.trucks !== null && previous.trucks !== summary.trucks)
    key.append(
      element(
        "span",
        "parking-bar__key-item parking-bar__key-item--was",
        `was ${demandText(previous)}`,
      ),
    );
  wrap.append(head, bar, key);
  if (summary.recorded)
    wrap.append(element("p", "parking-bar__record", summary.recorded));
  const target = segmentShares(summary);
  if (previous && previous.capacity === summary.capacity) {
    applyShares(bar, segmentShares(previous));
    bar.classList.add("is-animating");
    requestAnimationFrame(() =>
      requestAnimationFrame(() => applyShares(bar, target)),
    );
  } else applyShares(bar, target);
  return wrap;
}
