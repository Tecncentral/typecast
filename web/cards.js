import { el, button, assetUrl } from "./utils.js";
import {
  availability,
  createShotViewer,
  fitStatus,
  logisticsStatus,
  openEvidenceDrawer,
  quantity,
  sourceStatuses,
  statusTag,
} from "./drawer.js";
let cardSerial = 0;
function metric(label, value, className = "") {
  const item = el("div", undefined, `pick-metric ${className}`.trim());
  item.append(el("dt", label), el("dd", value));
  return item;
}
function previousPick(previousPicks, id) {
  return Array.isArray(previousPicks)
    ? previousPicks.find((pick) => pick.property?.property_id === id)
    : undefined;
}
function rankChange(pick, previousPicks) {
  if (!Array.isArray(previousPicks) || !previousPicks.length) return null;
  const previous = previousPick(previousPicks, pick.property?.property_id);
  if (!previous) return el("span", "New to shortlist", "rank-change");
  if (previous.rank === pick.rank)
    return el("span", "Rank unchanged", "rank-change rank-unchanged");
  return el(
    "span",
    `Rank ${previous.rank} to ${pick.rank}`,
    `rank-change ${previous.rank > pick.rank ? "rank-up" : "rank-down"}`,
  );
}
function reasonSummary(pick) {
  const supplied = pick.reason?.trim() || "";
  if (supplied && supplied.length <= 90) return supplied;
  const lead = supplied.split(";")[0];
  const blocked = /^blocked alternative$/i.test(lead);
  if (lead && lead.length <= 90 && !blocked && !/^(CoStar|Matterport|Vexcel):/i.test(lead))
    return lead;
  const fit = fitStatus(pick);
  const logistics = pick.logistics ?? {};
  const parking = logisticsStatus(logistics, "parking");
  return [
    blocked ? lead : null,
    fit === "fits" ? "Shot fits" : fit === "tight" ? "Shot is tight" : "Fit unknown",
    logistics.truck_spaces == null
      ? "Truck capacity unknown"
      : `${quantity(logistics.truck_spaces, "", 0)} truck spaces · ${parking}`,
  ].filter(Boolean).join(" · ");
}
function parkingSummary(logistics, property) {
  const section = el("section", undefined, "card-logistics");
  const heading = el("div", undefined, "card-section-heading");
  heading.append(
    el("h4", "Crew logistics"),
    statusTag(
      logisticsStatus(logistics, "parking"),
      logisticsStatus(logistics, "parking"),
    ),
  );
  section.append(heading);
  const content = el(
    "div",
    undefined,
    `card-parking-content ${logistics.aerial_image_path ? "has-aerial" : ""}`,
  );
  const metrics = el("dl", undefined, "parking-metrics");
  metrics.append(
    metric("Truck spaces", quantity(logistics.truck_spaces, "", 0)),
    metric("Crew cars", quantity(logistics.car_spaces, "", 0)),
  );
  metrics.append(
    metric(
      "Walk",
      `${quantity(logistics.walk_m, " m")} · ${logisticsStatus(logistics, "walk")}`,
      "walk-metric",
    ),
  );
  content.append(metrics);
  if (logistics.aerial_image_path) {
    const aerial = el("figure", undefined, "card-aerial");
    const image = el("img");
    image.src = assetUrl(logistics.aerial_image_path);
    image.alt = `Aerial parking evidence at ${property.address || "this location"}`;
    image.loading = "lazy";
    const fallback = el(
      "p",
      "Aerial unavailable",
      "image-fallback aerial-fallback",
    );
    fallback.hidden = true;
    image.addEventListener("error", () => {
      image.hidden = true;
      fallback.hidden = false;
    });
    aerial.append(image, fallback, el("figcaption", "Vexcel aerial"));
    content.append(aerial);
  }
  section.append(content);
  const noise = el("div", undefined, "card-noise");
  const status = logisticsStatus(logistics, "noise"),
    flags = logistics.noise_flags ?? [];
  noise.append(el("span", "Noise", "noise-label"), statusTag(status, status));
  if (flags.length) {
    const list = el("ul", undefined, "noise-flags");
    for (const flag of flags) list.append(el("li", flag));
    noise.append(list);
  } else
    noise.append(
      el(
        "p",
        status === "unknown" ? "Conditions unknown" : "No flags reported",
      ),
    );
  section.append(noise);
  return section;
}

/** Render supplied evidence without fetching, drafting or inventing results. */
export function renderCards(
  host,
  picks,
  { config = {}, onDraft, previousPicks } = {},
) {
  const nodes = [];
  for (const pick of Array.isArray(picks) ? picks : []) {
    const property = pick.property ?? {},
      fit = pick.shot_fit ?? {},
      logistics = pick.logistics ?? {};
    const article = el("article", undefined, "pick-card");
    article.dataset.propertyId = property.property_id || "";
    article.dataset.rank = String(pick.rank ?? "");
    const titleId = `pick-title-${++cardSerial}`;
    article.setAttribute("aria-labelledby", titleId);
    const frame = createShotViewer(pick.shots, { address: property.address });
    const frameFit = fitStatus(pick);
    frame.element
      .querySelector(".shot-stage")
      .append(
        el(
          "span",
          frameFit === "fits"
            ? "Shot fits"
            : frameFit === "tight"
              ? "Shot is tight"
              : "Fit unknown",
          `fit-badge fit-${frameFit} frame-fit`,
        ),
      );
    const top = el("header", undefined, "pick-header");
    const titleRow = el("div", undefined, "pick-title-row");
    const title = el("h3", property.address || "Address unknown");
    title.id = titleId;
    const rank = el(
      "span",
      String(pick.rank ?? "—").padStart(2, "0"),
      "pick-rank",
    );
    rank.setAttribute("aria-label", `Rank ${pick.rank ?? "unknown"}`);
    titleRow.append(rank, title);
    const meta = el("div", undefined, "pick-topline");
    const state = availability(property);
    meta.append(
      el("span", state.text, `availability availability-${state.status}`),
    );
    const changed = rankChange(pick, previousPicks);
    if (changed) meta.append(changed);
    top.append(
      titleRow,
      el(
        "p",
        [
          property.city,
          property.type,
          property.year_built ? `Built ${property.year_built}` : "Era unknown",
        ]
          .filter(Boolean)
          .join(" · "),
        "pick-property-meta",
      ),
      meta,
    );
    const content = el("div", undefined, "pick-body");
    const reason = el("details", undefined, "pick-rationale");
    const reasonHeading = el("summary", undefined, "pick-reason");
    reasonHeading.append(
      el("span", reasonSummary(pick)),
      el("span", "Full reason", "reason-disclosure-label"),
    );
    reason.append(
      reasonHeading,
      el("p", pick.reason || "No ranking reason was supplied.", "full-reason"),
    );
    content.append(reason);
    const physical = el("section", undefined, "card-fit");
    const status = fitStatus(pick);
    const fitHeading = el("div", undefined, "card-section-heading");
    fitHeading.append(
      el("h4", "Physical fit"),
      el(
        "span",
        status === "fits"
          ? "Shot fits"
          : status === "tight"
            ? "Shot is tight"
            : "Fit unknown",
        `fit-badge fit-${status}`,
      ),
    );
    const geometry = el("dl", undefined, "fit-metrics");
    geometry.append(
      metric("Depth needed", quantity(fit.needed_depth_m, " m", 2)),
      metric("Available", quantity(fit.have_depth_m, " m", 2)),
      metric("Ceiling", quantity(fit.ceiling_m, " m")),
    );
    physical.append(fitHeading, geometry);
    content.append(physical);
    const sources = el("div", undefined, "source-chips");
    sources.setAttribute("aria-label", "Evidence status by source");
    for (const source of sourceStatuses(pick)) {
      const chip = statusTag(
        `${source.label} · ${source.status}`,
        source.status,
        "source-chip",
      );
      chip.title = `${source.count} supplied ${source.count === 1 ? "claim" : "claims"}; see every claim in View evidence`;
      sources.append(chip);
    }
    content.append(sources, parkingSummary(logistics, property));
    const skeptic = el("section", undefined, "card-skeptic");
    skeptic.append(el("h4", "Skeptic review"));
    const prior = previousPick(previousPicks, property.property_id);
    const extraNotes = el("details", undefined, "skeptic-more");
    const notes = pick.skeptic_notes ?? [];
    let extraCount = 0;
    for (const [index, note] of notes.entries()) {
      const isNew = prior && !prior.skeptic_notes?.includes(note);
      const line = el(
        "p",
        undefined,
        `skeptic-note ${/^no objection\.?$/i.test(note.trim()) ? "skeptic-clear" : ""}`,
      );
      if (isNew)
        line.append(el("span", "New · ", "new-objection"));
      line.append(document.createTextNode(note));
      if (index < 3 || isNew) skeptic.append(line);
      else {
        extraNotes.append(line);
        extraCount += 1;
      }
    }
    if (extraCount) {
      extraNotes.prepend(el("summary", `${extraCount} more caveats`));
      skeptic.append(extraNotes);
    }
    if (!pick.skeptic_notes?.length)
      skeptic.append(
        el("p", "No review supplied", "skeptic-note skeptic-unknown"),
      );
    content.append(skeptic);
    const footer = el("footer", undefined, "pick-actions");
    const detail = button(
      "View evidence",
      () =>
        openEvidenceDrawer(pick, {
          config,
          onDraft,
          initialShotIndex: frame.getIndex(),
        }),
      "view-evidence",
    );
    const draftError = el("p", "", "card-draft-status");
    draftError.setAttribute("role", "status");
    const draft = button(
      "Draft note",
      async () => {
        if (typeof onDraft !== "function") return;
        draft.disabled = true;
        draft.setAttribute("aria-busy", "true");
        draftError.textContent = "";
        try {
          const message = await onDraft(pick);
          if (typeof message === "string" && message.trim()) {
            draftError.textContent = message;
            draftError.dataset.state =
              message === "Saved as a local draft, not sent"
                ? "saved"
                : "error";
          }
        } catch {
          draftError.textContent = "Draft could not be saved. Try again.";
        } finally {
          draft.disabled = false;
          draft.removeAttribute("aria-busy");
        }
      },
      "draft-note",
    );
    draft.disabled = typeof onDraft !== "function";
    footer.append(detail, draft, draftError);
    article.append(frame.element, top, content, footer);
    nodes.push(article);
  }
  host.replaceChildren(...nodes);
}
