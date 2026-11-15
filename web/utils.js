export function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
export function button(text, action, className) {
  const node = el("button", text, className);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}
export function assetUrl(path) {
  if (typeof path !== "string" || !path.trim()) return "";
  const clean = path.replace(/^\/+/, "");
  if (!/^(cache|mocks)\//.test(clean) || clean.includes("\\")) return "";
  try {
    if (
      decodeURIComponent(clean)
        .split("/")
        .some((part) => part === ".." || part === ".")
    )
      return "";
    const url = new URL("/" + clean, location.origin);
    return url.origin === location.origin ? url.pathname : "";
  } catch {
    return "";
  }
}
export function formatNumber(value, maxDecimals = 1) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-US", { maximumFractionDigits: maxDecimals })
    : "unknown";
}

/**
 * Readable source text: round over-precise measurements, write m², drop a
 * midnight timestamp. Coordinates and counts without units are untouched.
 */
export function tidyText(text) {
  if (typeof text !== "string") return text;
  return text
    .replace(
      /(\d+\.\d{2,})(\s?)(m²|m2|m\b|sq ?ft|sf\b)/g,
      (_, value, space, unit) => {
        const number = Number(value);
        const rounded = number >= 100 ? Math.round(number) : Math.round(number * 10) / 10;
        return rounded.toLocaleString("en-US") + (space || " ") + unit;
      },
    )
    .replace(/(\d)(\s?)m2\b/g, "$1$2m²")
    .replace(/(\d{4}-\d{2}-\d{2})T00:00:00(?:\.0+)?/g, "$1");
}

/** The pipeline prefixes picks with open blockers; say what that means. */
export function readableReason(reason) {
  if (typeof reason !== "string" || !reason) return reason;
  return tidyText(
    reason.replace(/^Blocked alternative;\s*/, "Open checks before booking (see caveats). "),
  );
}
