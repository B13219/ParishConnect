import type { OrganizationPath, TermPresentation } from "../types/api";
// The server resolves denomination/snapshot policy. Clients only select a locale.
export function termView(presentation?: TermPresentation, locale = "en") {
  return presentation?.[locale === "sw" ? "sw" : "en"] || presentation?.en;
}
export function ancestryText(path: OrganizationPath = [], locale = "en", full = false) {
  return (full ? path : path.slice(0, -1).slice(-2)).map(unit => {
    const view = termView(unit.presentation, locale);
    return `${view?.name || unit.name || "Organization"} — ${view?.label || unit.labels?.en || unit.level_key}`;
  }).join(" · ");
}
