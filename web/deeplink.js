// Open a search from a link: /app/?scene=<encoded>&autorun=1 fills the scene box and starts the normal
// live search, exactly as if the run button were pressed. Without both parameters this does nothing.
// It is a second, live search, not a saved thread. The scene goes in as plain text (textarea value).
// Loaded after app.js so its submit handler already exists.
const MAX_SCENE_CHARS = 2000;

const params = new URLSearchParams(location.search);
const scene = (params.get("scene") || "").trim().slice(0, MAX_SCENE_CHARS);

if (scene && params.get("autorun") === "1") {
  const box = document.getElementById("scene");
  const form = document.getElementById("scene-form");
  if (box && form) {
    box.value = scene;
    form.requestSubmit();
    // A reload keeps the scene in the box but does not search again.
    params.delete("autorun");
    history.replaceState(null, "", `${location.pathname}?${params}${location.hash}`);
  }
}

// An exterior brief (ext=) never runs from a link: it is a billable Vexcel search. Show a hand-off to the
// outdoors page, which only pre-fills its box (oblique.js); the user presses Search.
const ext = (params.get("ext") || "").trim().slice(0, 300);
if (ext) {
  const handoff = document.createElement("p");
  handoff.id = "ext-handoff";
  const next = new URLSearchParams({ q: ext });
  if (params.get("city")) next.set("city", params.get("city"));
  const link = document.createElement("a");
  link.href = `./oblique.html?${next}`;
  link.textContent = "Open the exterior search";
  handoff.append(`Exterior search ready: ${ext.replace(/\.+$/, "")}. It does not run until you open it and press Search (a live Vexcel call). `, link);
  document.getElementById("scene-form")?.after(handoff);
}
