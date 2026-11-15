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
