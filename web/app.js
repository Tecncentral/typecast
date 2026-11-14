import { el, button, assetUrl, formatNumber } from "./utils.js";
import { SCENES } from "./scenes.js";
import { renderCards } from "./cards.js";
import { renderMap } from "./map.js";
import { Progress } from "./progress.js";
import { Descent } from "./descent.js";
const $ = (selector) => document.querySelector(selector);
const progress = new Progress();
const descent = new Descent($("#location-map"));
let config = null,
  response = null,
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
  $("#activity").open = true;
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

function renderChanges(before, after, message) {
  const host = $("#changes");
  host.replaceChildren(el("h3", "What changed · " + message));
  const list = el("ul"),
    old = new Map(before.picks.map((p) => [p.property.property_id, p])),
    ids = new Set(after.picks.map((p) => p.property.property_id));
  let moved = false;
  for (const pick of after.picks) {
    const previous = old.get(pick.property.property_id),
      name = pick.property.address;
    if (!previous) {
      list.append(el("li", name + " joined at rank " + pick.rank + "."));
      moved = true;
    } else {
      if (previous.rank !== pick.rank) {
        list.append(
          el("li", name + ": rank " + previous.rank + " → " + pick.rank + "."),
        );
        moved = true;
      }
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
    }
    for (const note of pick.skeptic_notes || [])
      if (
        note.trim().toLowerCase() !== "no objection." &&
        !(previous?.skeptic_notes || []).includes(note)
      )
        list.append(
          el("li", name + " · New objection: " + note, "change-objection"),
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
function showResult(data, previous, message) {
  validateResult(data);
  response = data;
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
  const current = response.picks.find(
    (value) =>
      value.property.property_id === pick.property.property_id &&
      value.rank === pick.rank,
  );
  if (!current) return;
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
  const node = button(preset.label, () => {
    $("#scene").value = preset.scene;
    document
      .querySelectorAll("#scene-buttons button")
      .forEach((item) =>
        item.setAttribute("aria-pressed", String(item === node)),
      );
    scout();
  });
  node.setAttribute("aria-pressed", "false");
  $("#scene-buttons").append(node);
}
$("#scene").addEventListener("input", () =>
  document
    .querySelectorAll("#scene-buttons button")
    .forEach((item) => item.setAttribute("aria-pressed", "false")),
);
$("#scene-form").addEventListener("submit", scout);
$("#refine-form").addEventListener("submit", refine);
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
