import { el, button, assetUrl, tidyText, readableReason } from "./utils.js";
import {
  availability,
  createShotViewer,
  fitStatus,
  logisticsStatus,
  numberKnown,
  openEvidenceDrawer,
  quantity,
  sourceStatuses,
  statusTag,
} from "./drawer.js";
let cardSerial = 0;
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
function chevron() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", "disclosure-chevron");
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute("d", "M9 5l7 7-7 7");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.8");
  svg.append(path);
  return svg;
}
function disclosure(className, label, extraClass = "") {
  const details = el("details", undefined, className);
  const summary = el("summary", undefined, extraClass);
  summary.append(chevron(), el("span", label));
  details.append(summary);
  return details;
}
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
/** "OSM: Rail about 68 m from property coordinate; ..." -> "Rail 68 m away" */
function shortFlag(flag) {
  const match = /(Freeway|Rail|Airport\/runway)\s+about\s+(\d+)\s*m/i.exec(flag || "");
  return match ? `${match[1]} ${match[2]} m away` : null;
}
/** Known values only, one row each; a missing value simply has no row. */
function specRows(pick, logistics, property) {
  const fit = pick.shot_fit ?? {};
  const wrap = el("div", undefined, "pick-specs");
  const list = el("dl");
  const add = (label, value, note) => {
    const row = el("div", undefined, "spec-row");
    const dd = el("dd");
    dd.append(document.createTextNode(value));
    if (note) dd.append(el("span", note, "spec-note"));
    row.append(el("dt", label), dd);
    list.append(row);
  };
  const status = fitStatus(pick);
  if (numberKnown(fit.needed_depth_m)) {
    const need = `needs ${quantity(fit.needed_depth_m, " m", 1)} depth`;
    add("Shot", status === "fits" ? `Fits · ${need}` : status === "tight" ? `Tight · ${need}` : need);
  }
  if (numberKnown(logistics.truck_spaces) || numberKnown(logistics.car_spaces)) {
    const parts = [
      numberKnown(logistics.truck_spaces) ? plural(logistics.truck_spaces, "truck") : null,
      numberKnown(logistics.car_spaces) ? plural(logistics.car_spaces, "car") : null,
    ].filter(Boolean).join(" · ");
    const state = logisticsStatus(logistics, "parking");
    add("Parking", parts, state === "measured" ? null : state === "estimated" ? "estimate" : "unverified");
  }
  const flags = (logistics.noise_flags ?? []).map(shortFlag).filter(Boolean);
  if (flags.length) add("Noise", flags.join(" · "), "map screen");
  wrap.append(list);
  if (logistics.aerial_image_path) {
    const image = el("img", undefined, "pick-aerial");
    image.src = assetUrl(logistics.aerial_image_path);
    image.alt = `Vexcel aerial with the parking estimate at ${property.address || "this location"}`;
    image.loading = "lazy";
    image.addEventListener("error", () => image.remove());
    wrap.append(image);
  }
  return wrap;
}
/** The honesty signal, said once: what no source supplied. */
function gaps(pick, logistics, property) {
  const fit = pick.shot_fit ?? {};
  const out = [];
  if (availability(property).status === "unknown") out.push("availability");
  if (!numberKnown(fit.have_depth_m)) out.push("room depth");
  if (!numberKnown(fit.ceiling_m)) out.push("ceiling");
  if (fitStatus(pick) === "unknown" && numberKnown(fit.have_depth_m) && numberKnown(fit.ceiling_m)) out.push("shot fit");
  if (!numberKnown(logistics.truck_spaces) && !numberKnown(logistics.car_spaces)) out.push("parking");
  if (!numberKnown(logistics.walk_m)) out.push("walk to parking");
  if (logisticsStatus(logistics, "noise") === "unknown") out.push("noise");
  return out;
}
function rationale(pick, logistics) {
  const details = disclosure("pick-rationale", "Why this pick", "pick-reason");
  const body = el("div", undefined, "disclosure-body");
  const sources = el("div", undefined, "source-chips");
  sources.setAttribute("aria-label", "Evidence status by source");
  for (const source of sourceStatuses(pick)) {
    const chip = statusTag(`${source.label} · ${source.status}`, source.status, "source-chip");
    chip.title = `${source.count} supplied ${source.count === 1 ? "claim" : "claims"}; see every claim in View evidence`;
    sources.append(chip);
  }
  body.append(sources, el("p", readableReason(pick.reason) || "No ranking reason was supplied.", "full-reason"));
  const flags = logistics.noise_flags ?? [];
  if (flags.length) {
    const list = el("ul", undefined, "noise-flags");
    for (const flag of flags) list.append(el("li", flag));
    body.append(list);
  }
  details.append(body);
  return details;
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
    if (frameFit === "fits" || frameFit === "tight")
      frame.element
        .querySelector(".shot-stage")
        .append(el("span", frameFit === "fits" ? "Shot fits" : "Shot is tight", `fit-badge fit-${frameFit} frame-fit`));
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
    const state = availability(property);
    const metaLine = el("p", undefined, "pick-property-meta");
    metaLine.append(
      document.createTextNode([property.city, property.type, property.year_built].filter(Boolean).join(" · ")),
    );
    if (state.status !== "unknown")
      metaLine.append(el("span", state.text, `availability availability-${state.status}`));
    const changed = rankChange(pick, previousPicks);
    if (changed) metaLine.append(changed);
    top.append(titleRow, metaLine);
    const content = el("div", undefined, "pick-body");
    content.append(specRows(pick, logistics, property));
    const missing = gaps(pick, logistics, property);
    if (missing.length) {
      const line = el("p", undefined, "pick-gaps");
      line.title = "No source supplied these. Nothing is guessed.";
      line.append(el("span", "Confirm on site", "gaps-label"), document.createTextNode(missing.join(" · ")));
      content.append(line);
    }
    content.append(rationale(pick, logistics));
    const skeptic = el("section", undefined, "card-skeptic");
    const prior = previousPick(previousPicks, property.property_id);
    const notes = pick.skeptic_notes ?? [];
    const isClear = (note) => /^no objection\.?$/i.test(note.trim());
    const noteLine = (note, lead = false) => {
      const isNew = prior && !prior.skeptic_notes?.includes(note);
      const line = el("p", undefined, `skeptic-note ${isClear(note) ? "skeptic-clear" : ""} ${lead ? "skeptic-lead" : ""}`.trim());
      if (lead) line.append(el("span", "Skeptic", "skeptic-label"));
      if (isNew) line.append(el("span", "New · ", "new-objection"));
      line.append(document.createTextNode(tidyText(note)));
      return line;
    };
    if (!notes.length) skeptic.append(el("p", "No review supplied", "skeptic-note skeptic-unknown"));
    else {
      const leadIndex = notes.findIndex((note) => !isClear(note));
      const lead = leadIndex >= 0 ? notes[leadIndex] : notes[0];
      skeptic.append(noteLine(lead, true));
      const rest = notes.filter((_, index) => index !== (leadIndex >= 0 ? leadIndex : 0));
      if (rest.length) {
        const more = disclosure("skeptic-more", plural(rest.length, "more caveat"));
        const body = el("div", undefined, "disclosure-body");
        for (const note of rest) body.append(noteLine(note));
        more.append(body);
        skeptic.append(more);
      }
    }
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
