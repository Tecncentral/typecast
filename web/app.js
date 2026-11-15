import { el, button, assetUrl, formatNumber, tidyText } from "./utils.js";
import { SCENES } from "./scenes.js";
import { renderCards } from "./cards.js";
import { renderMap, focusMapPick } from "./map.js";
import { renderBudget } from "./budget.js";
import { arrangeBudget } from "./costs.js";
import {
  parkingBar,
  parkingSummary,
  vehiclesOf,
  demandText,
} from "./parking.js";
import { Progress } from "./progress.js";
import { Descent } from "./descent.js";
import { parseScript, requestPlan, renderPlan, PLANNER_LIMIT } from "./script-mode.js";
const $ = (selector) => document.querySelector(selector);
const progress = new Progress();
const descent = new Descent($("#location-map"));
let config = null,
  response = null,
  original = null, // the shortlist before any follow-up, for "Back to original"
  serverPicks = null, // the service's current saved shortlist for this thread (drafts use its ranks)
  busy = false,
  stream = null,
  ticker = null,
  deadline = null,
  started = 0,
  mapCleanup = null,
  draftBusy = false;
async function request(path, body, timeout = 15000) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), timeout);
  try {
    const result = await fetch(path, {
      signal: controller.signal,
      cache: "no-store",
      ...(body === undefined
        ? {}
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
    });
    let data;
    try {
      data = await result.json();
    } catch {
      throw Error(
        "The service returned an unreadable response. Please try again.",
      );
    }
    if (!result.ok)
      throw Error(
        result.status === 404 && path === "/refine"
          ? "This scouting session has expired. Scout the scene again to continue."
          : `The request failed (${result.status}). Please try again.`,
      );
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw Error(
        "The service is taking too long to respond. Please try again.",
      );
    if (error instanceof TypeError)
      throw Error(
        "Cannot reach the local scouting service. Check that it is running, then try again.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
function metadata(mode, engine) {
  const value = ["mock", "live", "mixed"].includes(mode) ? mode : "unknown";
  $("#source-mode").textContent = value.toUpperCase();
  $("#source-mode").dataset.mode = value;
  $("#engine").textContent = ["fixed", "deep"].includes(engine)
    ? engine.toUpperCase() + " ENGINE"
    : "ENGINE UNKNOWN";
}
async function loadConfig() {
  config = await request("/config");
  if (
    !["mock", "live", "mixed"].includes(config.mode) ||
    !["fixed", "deep"].includes(config.engine)
  )
    throw Error(
      "The scouting configuration is unavailable. Try again when the service is ready.",
    );
  metadata(config.mode, config.engine);
  $("#mode-note").textContent =
    config.mode === "mock"
      ? "MOCK MODE · Synthetic fixture locations and images. No live property search."
      : config.mode === "mixed"
        ? "MIXED SOURCES · Source settings disagree. Restart the service before scouting."
        : "LIVE MODE · Private property, interior, and aerial evidence. Availability does not establish filming permission.";
  return config;
}
function showError(message) {
  $("#api-error").textContent = message;
  $("#api-error").hidden = false;
}
function controls() {
  $("#run-button").disabled = busy || draftBusy;
  $("#refine-button").disabled = busy || draftBusy || !response;
  $("#scene").disabled = busy;
  $("#refine-message").disabled = busy;
  document
    .querySelectorAll("#scene-buttons button")
    .forEach((node) => (node.disabled = busy || draftBusy));
  $("#results").inert = busy;
}
function tick() {
  const seconds = Math.floor((performance.now() - started) / 1000);
  $("#elapsed").textContent = seconds + "s";
  $("#slow-note").hidden = seconds < 8;
  if (seconds >= 8)
    $("#slow-note").textContent =
      seconds >= 60
        ? "Still waiting for the service. The elapsed clock is real; no new result has arrived."
        : "Still scouting. Live runs can take about 10s on the fixed engine or 40s on the deep engine.";
}
function begin(refine = false) {
  descent.cancel("superseded", false);
  busy = true;
  controls();
  $("#api-error").hidden = true;
  $("#draft-status").hidden = true;
  $("#run-section").hidden = false;
  $("#welcome").hidden = true;
  $("#run-section").className = "run-section is-running";
  $("#run-status").textContent = refine
    ? "Updating the shortlist…"
    : "Scouting your scene…";
  $("#trace-link").hidden = true;
  progress.reset(refine);
  started = performance.now();
  tick();
  ticker = setInterval(tick, 500);
}
function finish(error = false) {
  if (stream) {
    stream.close();
    stream = null;
  }
  clearInterval(ticker);
  clearTimeout(deadline);
  tick();
  $("#slow-note").hidden = true;
  busy = false;
  controls();
  $("#run-section").className =
    "run-section " + (error ? "is-failed" : "is-complete");
  if (!error) progress.finish();
}
function fail(error) {
  finish(true);
  $("#run-status").textContent = "Scouting interrupted";
  showError(
    error.message + (response ? " Your previous shortlist remains below." : ""),
  );
}
function validateResult(data) {
  if (!data || !Array.isArray(data.picks) || typeof data.thread_id !== "string")
    throw Error(
      "The service returned an incomplete shortlist. Please try again.",
    );
  return data;
}
function renderRelaxations(data) {
  const host = $("#relaxations");
  host.replaceChildren();
  const items = [...new Set((data.gave_up || []).map(String))];
  const notices = (data.events || [])
    .filter((event) => event.type === "relaxed")
    .map((event) => event.text);
  host.hidden = !items.length && !notices.length;
  if (host.hidden) return;
  host.append(
    el(
      "summary",
      items.length
        ? items.length +
            " preference" +
            (items.length === 1 ? "" : "s") +
            " relaxed · " +
            items.join(", ")
        : "Relaxed preferences — inspect the changes",
    ),
  );
  const content = el("div", null, "relaxation-content");
  for (const item of items)
    content.append(el("p", "Relaxed preference: " + item));
  for (const notice of [...new Set(notices)]) content.append(el("p", notice));
  host.append(content);
  host.open = !data.picks.length;
}

function parkingChanged(before, after) {
  const old = new Map(before.picks.map((p) => [p.property.property_id, p]));
  return after.picks.some((pick) => {
    const previous = old.get(pick.property.property_id);
    return (
      !previous ||
      previous.logistics?.truck_spaces !== pick.logistics?.truck_spaces ||
      previous.logistics?.car_spaces !== pick.logistics?.car_spaces
    );
  });
}
function renderParkingShift(before, after) {
  const was = vehiclesOf(before),
    now = vehiclesOf(after),
    old = new Map(before.picks.map((p) => [p.property.property_id, p]));
  const block = el("div", null, "change-parking");
  // A lot that no longer holds the crew is the clearest picture of the change.
  const afterIds = new Set(after.picks.map((p) => p.property.property_id));
  const shortLeaver = before.picks.find(
    (pick) =>
      !afterIds.has(pick.property.property_id) &&
      parkingSummary(pick, now).fits === false,
  );
  const focus = shortLeaver || after.picks[0];
  const top = el("div", null, "change-parking__top");
  top.append(
    el(
      "p",
      was.trucks === now.trucks && was.cars === now.cars
        ? "Parking for " + demandText(now) + " · estimated from Vexcel lots"
        : "Crew vehicles " + demandText(was) + " → " + demandText(now),
      "change-parking__title",
    ),
    button(
      shortLeaver ? "See the short lot on the map" : "See the lots on the map",
      () => {
        $("#map-section").scrollIntoView({
          block: "start",
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "instant"
            : "smooth",
        });
        focusMapPick($("#location-map"), focus?.property.property_id);
      },
      "change-parking__map",
    ),
  );
  const grid = el("div", null, "change-parking__grid");
  for (const pick of after.picks) {
    const card = el("div", null, "change-parking__pick");
    const previous = old.get(pick.property.property_id);
    card.append(
      el(
        "p",
        pick.rank + " · " + pick.property.address + (previous ? "" : " · new"),
        "change-parking__name",
      ),
      parkingBar(parkingSummary(pick, now), {
        previous: previous ? parkingSummary(previous, was) : undefined,
      }),
    );
    grid.append(card);
  }
  for (const pick of before.picks) {
    if (afterIds.has(pick.property.property_id)) continue;
    const card = el("div", null, "change-parking__pick change-parking__pick--left");
    card.append(
      el("p", "Left · " + pick.property.address, "change-parking__name"),
      parkingBar(parkingSummary(pick, now), {
        previous: parkingSummary(pick, was),
      }),
    );
    grid.append(card);
  }
  block.append(top, grid);
  return block;
}
function renderChanges(before, after, message) {
  const host = $("#changes");
  host.replaceChildren(el("h3", "What changed · " + message));
  const showParking = parkingChanged(before, after);
  if (showParking) host.append(renderParkingShift(before, after));
  const list = el("ul"),
    old = new Map(before.picks.map((p) => [p.property.property_id, p])),
    ids = new Set(after.picks.map((p) => p.property.property_id));
  let moved = false;
  for (const pick of after.picks) {
    const previous = old.get(pick.property.property_id),
      name = pick.property.address;
    if (!previous) {
      // A newcomer's standing caveats are on its card, not new objections.
      list.append(
        el(
          "li",
          name +
            " joined at rank " +
            pick.rank +
            "." +
            (pick.skeptic_notes?.length
              ? " Its " +
                pick.skeptic_notes.length +
                " caveats are on its card."
              : ""),
        ),
      );
      moved = true;
      continue;
    }
    if (previous.rank !== pick.rank) {
      list.append(
        el("li", name + ": rank " + previous.rank + " → " + pick.rank + "."),
      );
      moved = true;
    }
    if (!showParking)
      for (const [key, label] of [
        ["truck_spaces", "truck spaces"],
        ["car_spaces", "car spaces"],
      ])
        if (previous.logistics?.[key] !== pick.logistics?.[key])
          list.append(
            el(
              "li",
              name +
                ": " +
                formatNumber(previous.logistics?.[key]) +
                " → " +
                formatNumber(pick.logistics?.[key]) +
                " " +
                label +
                ".",
            ),
          );
    for (const note of pick.skeptic_notes || [])
      if (
        note.trim().toLowerCase() !== "no objection." &&
        !(previous.skeptic_notes || []).includes(note)
      )
        list.append(
          el("li", name + " · New objection: " + tidyText(note), "change-objection"),
        );
  }
  for (const pick of before.picks)
    if (!ids.has(pick.property.property_id)) {
      list.append(
        el(
          "li",
          pick.property.address +
            " left the shortlist. Its earlier frames are kept below.",
        ),
      );
      moved = true;
    }
  if (!moved) list.prepend(el("li", "Rank order unchanged."));
  if (before.engine !== after.engine)
    list.append(
      el("li", "This refinement used the " + after.engine + " engine."),
    );
  if (!list.childElementCount)
    list.append(
      el(
        "li",
        "No rank, parking allocation, or objection changes were reported.",
      ),
    );
  host.append(list);
  host.hidden = false;
}
function remember(data, message) {
  const snapshot = el("section", null, "history-snapshot");
  snapshot.append(
    el(
      "p",
      "Before “" +
        message +
        "” · " +
        String(data.source_mode || "unknown").toUpperCase() +
        " · " +
        String(data.engine || "unknown").toUpperCase(),
      "history-caption",
    ),
  );
  const grid = el("div", null, "history-grid");
  for (const pick of data.picks) {
    const card = el("article", null, "history-card"),
      images = el("div", null, "history-images");
    for (const shot of pick.shots || []) {
      const image = el("img");
      image.alt = "Earlier frame — " + pick.property.address;
      image.loading = "lazy";
      const src = assetUrl(shot.image_path),
        fallback = () =>
          image.replaceWith(
            el(
              "div",
              "Earlier frame unavailable",
              "history-image-fallback image-fallback",
            ),
          );
      image.addEventListener("error", fallback, { once: true });
      images.append(image);
      if (src) image.src = src;
      else fallback();
    }
    card.append(
      images,
      el("p", pick.property.address),
      el("small", "PREVIOUS RANK " + pick.rank),
    );
    grid.append(card);
  }
  snapshot.append(grid);
  $("#previous-results").prepend(snapshot);
  $("#history-section").hidden = false;
}
function showResult(data, previous, message, { restored = false } = {}) {
  validateResult(data);
  response = data;
  if (!restored) serverPicks = data.picks;
  if (!previous && !restored) original = data;
  $("#refine-reset").hidden = !original || data === original;
  document.body.classList.add("has-results");
  metadata(data.source_mode, data.engine);
  for (const event of data.events || []) progress.add(event);
  $("#shortlist-section").hidden = false;
  $("#empty-state").hidden = Boolean(data.picks.length);
  $("#shortlist-heading").textContent = data.picks.length
    ? data.picks.length +
      (data.picks.length === 1
        ? " location to consider"
        : " locations to consider")
    : "No matching locations";
  $("#result-meta").textContent =
    String(data.source_mode || "unknown").toUpperCase() +
    " · " +
    String(data.engine || "unknown").toUpperCase() +
    (typeof data.timings?.total_ms === "number"
      ? " · " + formatNumber(data.timings.total_ms / 1000, 1) + "s"
      : "");
  renderRelaxations(data);
  if (previous) {
    remember(previous, message);
    renderChanges(previous, data, message);
  } else {
    $("#changes").hidden = true;
    $("#previous-results").replaceChildren();
    $("#history-section").hidden = true;
  }
  renderCards($("#results"), data.picks, {
    config,
    onDraft: draftNote,
    previousPicks: previous?.picks,
  });
  $("#refine-section").hidden = false;
  if (mapCleanup) mapCleanup();
  $("#map-section").hidden = !data.picks.length;
  mapCleanup = data.picks.length
    ? renderMap($("#location-map"), data.picks, {
        vehicles: vehiclesOf(data),
        previous: previous ? { ...previous, message } : null,
        onSelect: (pick) => {
          const card = [
            ...document.querySelectorAll("#results .pick-card"),
          ].find(
            (node) => node.dataset.propertyId === pick.property.property_id,
          );
          if (card) {
            card.scrollIntoView({ behavior: "smooth", block: "center" });
            card.tabIndex = -1;
            card.focus({ preventScroll: true });
          }
        },
      })
    : null;
  $("#budget-section").hidden = !data.picks.length;
  renderBudget($("#budget"), $("#location-map"), data.picks);
  arrangeBudget();
  const trace = $("#trace-link");
  trace.hidden = true;
  trace.removeAttribute("href");
  if (data.trace_url) {
    try {
      const url = new URL(data.trace_url);
      if (url.protocol === "https:") {
        trace.href = url.href;
        trace.hidden = false;
      }
    } catch {}
  }
  finish();
  if (previous) {
    requestAnimationFrame(() =>
      $("#changes").scrollIntoView({
        block: "start",
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      }),
    );
  }
  $("#activity").open = false;
  $("#run-status").textContent = data.picks.length
    ? (previous ? "Shortlist updated" : "Shortlist ready") +
      " · " +
      data.picks.length +
      " locations"
    : "No match · review the relaxed preferences";
  descent.update(data, { autoplay: !previous });
}
async function scout(event) {
  event?.preventDefault();
  if (busy || draftBusy || !$("#scene-form").reportValidity()) return;
  const scene = $("#scene").value.trim();
  if (!scene) return;
  const scriptScenes = parseScript(scene);
  if (scriptScenes.length >= 2) return planScript(scriptScenes);
  $("#plan-section").hidden = true;
  begin();
  try {
    await loadConfig();
    if (config.mode === "mixed")
      throw Error(
        "Source settings disagree. Restart the service with one source mode before scouting.",
      );
    stream = new EventSource("/scout/stream?" + new URLSearchParams({ scene }));
    deadline = setTimeout(
      () =>
        fail(
          Error(
            "No final result arrived within three minutes. Please try again.",
          ),
        ),
      180000,
    );
    stream.addEventListener("agent", (message) => {
      try {
        const data = JSON.parse(message.data);
        progress.add(data);
        // One status line: the latest real step. The full log stays one click away.
        if (data.text && data.type !== "tool" && data.type !== "todo")
          $("#run-status").textContent = (data.agent ? data.agent.replace(/_/g, " ") + ": " : "") + tidyText(data.text).slice(0, 90);
        if (data.engine) metadata(config.mode, data.engine);
      } catch {
        fail(
          Error(
            "The service returned an unreadable activity event. Please try again.",
          ),
        );
      }
    });
    stream.addEventListener("result", (message) => {
      try {
        showResult(JSON.parse(message.data));
      } catch (error) {
        fail(error);
      }
    });
    stream.addEventListener("error", (message) => {
      if (!busy) return;
      let text = "The scouting connection was interrupted. Please try again.";
      if (message.data) {
        try {
          const data = JSON.parse(message.data);
          if (typeof data.message === "string") text = data.message;
        } catch {}
      }
      fail(Error(text));
    });
  } catch (error) {
    fail(error);
  }
}
async function refine(event) {
  event.preventDefault();
  if (busy || draftBusy || !response || !$("#refine-form").reportValidity())
    return;
  const message = $("#refine-message").value.trim();
  if (!message) return;
  const previous = response;
  begin(true);
  try {
    const data = validateResult(
      await request(
        "/refine",
        { thread_id: previous.thread_id, message },
        180000,
      ),
    );
    if (data.thread_id !== previous.thread_id)
      throw Error(
        "The service returned a different scouting session. Scout the scene again.",
      );
    showResult(data, previous, message);
  } catch (error) {
    fail(error);
  }
}
async function draftNote(pick) {
  if (busy || draftBusy || !response) return;
  // Drafts are saved by rank from the service's current shortlist. After "Back to original"
  // the screen and the service can differ, so look the building up there by property.
  const current = (serverPicks || response.picks).find(
    (value) => value.property.property_id === pick.property.property_id,
  );
  if (!current) {
    const status = $("#draft-status");
    status.hidden = false;
    status.textContent =
      "This building is not in the service's current shortlist after the follow-up, so no draft was saved. Refine or scout again to draft a note for it.";
    return status.textContent;
  }
  draftBusy = true;
  controls();
  const status = $("#draft-status");
  status.hidden = false;
  status.textContent = "Saving a local draft…";
  try {
    const data = await request(
      "/approve",
      {
        thread_id: response.thread_id,
        pick_rank: current.rank,
        decision: "yes",
      },
      120000,
    );
    if (data.status !== "draft_saved" || data.sent !== false) throw Error();
    status.textContent = "Saved as a local draft, not sent";
  } catch {
    status.textContent =
      "Could not confirm a saved local draft. Please try again.";
  } finally {
    draftBusy = false;
    controls();
  }
  return status.textContent;
}
for (const preset of SCENES) {
  // An example only fills the box; the director reads or edits it, then presses Scout.
  const node = button(preset.label, () => {
    const box = $("#scene");
    box.value = preset.scene;
    box.dispatchEvent(new Event("input", { bubbles: true }));
    document
      .querySelectorAll("#scene-buttons button")
      .forEach((item) =>
        item.setAttribute("aria-pressed", String(item === node)),
      );
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
    box.scrollTop = box.scrollHeight;
  });
  node.setAttribute("aria-pressed", "false");
  node.dataset.preview = preset.scene;
  $("#scene-buttons").append(node);
}
$("#scene").addEventListener("input", () =>
  document
    .querySelectorAll("#scene-buttons button")
    .forEach((item) => item.setAttribute("aria-pressed", "false")),
);
$("#scene-form").addEventListener("submit", scout);
$("#refine-form").addEventListener("submit", refine);
$("#refine-reset").addEventListener("click", () => {
  if (busy || draftBusy || !original || response === original) return;
  showResult(original, null, null, { restored: true });
  $("#run-status").textContent = "Back to the original shortlist · no new search";
  $("#shortlist-section").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
});
window.addEventListener("pagehide", () => {
  descent.cancel("hidden", false);
  stream?.close();
  clearInterval(ticker);
  clearTimeout(deadline);
  mapCleanup?.();
});
controls();
loadConfig().catch((error) => {
  metadata("unknown");
  $("#mode-note").textContent =
    "Configuration unavailable. Scout locations to retry the connection.";
  showError(error.message);
});

/* ---------- script mode: 2+ scene headings go to the production planner ---------- */
function updateScriptNote() {
  const n = parseScript($("#scene").value).length;
  $("#script-note").hidden = n < 2;
  $("#script-note").textContent = n < 2 ? ""
    : n <= PLANNER_LIMIT ? `Script: ${n} scenes detected. Scout plans locations across all of them.`
    : `Script: ${n} scenes detected. The planner takes ${PLANNER_LIMIT} at a time, so Scout plans scenes 1–${PLANNER_LIMIT}.`;
}
$("#scene").addEventListener("input", updateScriptNote);
updateScriptNote();

async function planScript(scenes) {
  begin();
  $("#run-status").textContent = `Planning locations for ${scenes.length} scenes`;
  $("#shortlist-section").hidden = true;
  $("#map-section").hidden = true;
  $("#budget-section").hidden = true;
  $("#refine-section").hidden = true;
  $("#history-section").hidden = true;
  $("#plan-section").hidden = true;
  try {
    await loadConfig();
    const data = await requestPlan(scenes);
    finish();
    renderPlan($("#plan-results"), data, scenes);
    $("#plan-section").hidden = false;
    $("#run-status").textContent = data.plans.length ? `Plan ready · ${scenes.length} scenes` : "No plan returned";
  } catch (error) {
    finish(true);
    $("#run-status").textContent = "Planning failed";
    showError(error.message + " Nothing was invented in its place.");
  }
}
