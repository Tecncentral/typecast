import { el, button } from "./utils.js";

// Core evidence is local; Showcase and its domain-bound SDK are optional remote
// dependencies, requested only when someone explicitly opens the source tour.
const BOOTSTRAP =
  "https://api.matterport.com/sdk/bootstrap/3.1.0-0-g1cd7e0997a/sdk.es6.js";
const modules = new Map();
function sdkModule(key) {
  if (!modules.has(key)) {
    const promise = import(
      `${BOOTSTRAP}?applicationKey=${encodeURIComponent(key)}`
    );
    modules.set(key, promise);
    promise.catch(() => modules.delete(key));
  }
  return modules.get(key);
}
function bounded(promise, duration) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("timeout")), duration);
    }),
  ]).finally(() => clearTimeout(timer));
}

export function createTour(shot, config = {}) {
  const section = el("section", undefined, "tour-section");
  section.append(el("h3", "Source 3D tour"));
  if (typeof shot?.model_id !== "string" || !shot.model_id.trim()) {
    section.append(
      el("p", "No source model is available for this frame.", "detail-muted"),
    );
    return { element: section, destroy() {} };
  }
  const url = new URL("https://my.matterport.com/show/");
  url.searchParams.set("m", shot.model_id);
  const link = el("a", "Open 3D tour", "source-tour-link");
  Object.assign(link, {
    href: url.href,
    target: "_blank",
    rel: "noopener noreferrer",
  });
  section.append(
    link,
    el(
      "p",
      "Opens at the model’s start. Image heading alignment is unverified.",
      "tour-caption",
    ),
  );
  const key =
    typeof config.matterport_sdk_key === "string"
      ? config.matterport_sdk_key.trim()
      : "";
  if (!key) return { element: section, destroy() {} };
  let alive = true,
    subscription,
    iframe;
  const message = el(
    "p",
    "The interactive tour needs an internet connection. Selected-frame heading alignment remains unverified.",
    "tour-status",
  );
  message.setAttribute("role", "status");
  const open = button(
    "Open interactive 3D tour",
    async () => {
      open.disabled = true;
      if (location.hostname === "127.0.0.1") {
        message.textContent =
          "Interactive tour access is configured for localhost. Open this viewer at localhost, or use the source tour link.";
        open.disabled = false;
        return;
      }
      message.textContent = "Connecting to the source tour…";
      iframe = el("iframe", undefined, "tour-iframe");
      iframe.title = "Matterport source tour for the selected frame";
      iframe.allow = "fullscreen";
      iframe.allowFullscreen = true;
      const embed = new URL(url);
      embed.searchParams.set("play", "1");
      embed.searchParams.set("applicationKey", key);
      iframe.src = embed.href;
      section.append(iframe);
      try {
        // Matches the verified bootstrap and exact-ID navigation in index/studio.js.
        const { connect } = await bounded(sdkModule(key), 25000);
        if (!alive) return;
        const sdk = await bounded(connect(iframe), 25000);
        if (!alive) return;
        const sweeps = new Map();
        subscription = sdk.Sweep.data.subscribe({
          onAdded: (id, value) => sweeps.set(id, value),
          onUpdated: (id, value) => sweeps.set(id, value),
          onRemoved: (id) => sweeps.delete(id),
        });
        const move = button(
          "Go to this scan point",
          async () => {
            move.disabled = true;
            delete message.dataset.confirmed;
            let stage = "readiness";
            try {
              message.textContent =
                "Waiting for the tour to finish opening or changing views…";
              // connect() can resolve during App.STARTING. A real live model
              // rejects moveTo then because its opening transition is active.
              // Follow observable readiness rather than guessing a load delay.
              await bounded(
                sdk.App.state.waitUntil(
                  (state) => state.phase === sdk.App.Phase.PLAYING,
                ),
                30000,
              );
              await bounded(
                sdk.Mode.transition.waitUntil(
                  (transition) =>
                    transition.from === null && transition.to === null,
                ),
                15000,
              );
              if (!alive) return;
              const requested = shot.sweep_id;
              const matches = requested
                ? [...sweeps.entries()].filter(([id, value]) =>
                    [id, value?.sid, value?.uuid].includes(requested),
                  )
                : [];
              if (matches.length !== 1) {
                message.textContent =
                  "This frame has no unique scan match in the tour. Explore manually or retry after it loads. Scan alignment is unverified.";
                return;
              }
              const [id, value] = matches[0];
              stage = "navigation";
              message.textContent = "Moving to the selected scan point…";
              await bounded(sdk.Sweep.moveTo(id, {}), 15000);
              const pose = await bounded(sdk.Camera.getPose(), 10000);
              if (!alive) return;
              if (
                [id, value?.sid, value?.uuid]
                  .filter(Boolean)
                  .includes(pose?.sweep)
              ) {
                message.textContent =
                  "Opens at this scan point · confirmed by the tour. Image heading alignment remains unverified.";
                message.dataset.confirmed = "true";
              } else {
                message.textContent =
                  "Scan movement finished, but the selected scan is not confirmed. Image heading alignment remains unverified.";
                delete message.dataset.confirmed;
              }
            } catch (error) {
              if (alive) {
                const changingViews =
                  stage === "readiness" ||
                  String(error?.message ?? error).includes(
                    "another transition was active",
                  );
                message.textContent = changingViews
                  ? "The tour is still opening or changing views. Wait for it to settle, then retry. Scan alignment remains unverified."
                  : "Scan navigation is unavailable. Explore manually or retry after it loads. Image heading alignment remains unverified.";
              }
            } finally {
              if (alive) move.disabled = false;
            }
          },
          "tour-move",
        );
        if (!alive) return;
        section.append(move);
        open.hidden = true;
        message.textContent =
          "Tour connected. Choose “Go to this scan point” to verify the frame’s scan. Image heading alignment remains unverified.";
      } catch {
        if (!alive) return;
        message.textContent =
          "Interactive tour could not connect. Use the source tour link, which opens at the model’s start. Image heading alignment remains unverified.";
        iframe?.remove();
        open.disabled = false;
        open.textContent = "Retry interactive 3D tour";
      }
    },
    "tour-open",
  );
  section.append(open, message);
  return {
    element: section,
    destroy() {
      alive = false;
      try {
        subscription?.cancel?.();
      } catch {
        /* Removing the iframe also ends its connection. */
      }
      iframe?.remove();
    },
  };
}
