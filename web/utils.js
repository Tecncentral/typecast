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
