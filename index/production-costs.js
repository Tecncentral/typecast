/* Deterministic USD scenario arithmetic, shared by the UI and Node tests. */
(function (root) {
  'use strict';
  function estimate(a, routeMinutes = null, complete = false) {
    const keys = ['visitsBefore', 'visitsAfter', 'scouts', 'scoutRate', 'onsiteHours', 'travelHours', 'visitMiles', 'mileRate', 'toolCost', 'crew', 'days', 'crewRate', 'baselineMinutes'];
    if (keys.some(k => typeof a[k] !== 'number' || !Number.isFinite(a[k]) || a[k] < 0 || a[k] > 1000000))
      return { error: 'Enter a finite, non-negative value for every cost assumption.' };
    if (!complete) return { error: 'Build a complete plan before estimating its savings.' };
    if (a.billing === 'daily' && (typeof a.dailyRate !== 'number' || !Number.isFinite(a.dailyRate) || a.dailyRate < 0 || a.dailyRate > 1000000))
      return { error: 'Enter a valid billable daily scouting rate.' };
    const perVisit = (a.billing === 'daily' ? a.scouts * a.dailyRate : a.scouts * a.scoutRate * (a.onsiteHours + a.travelHours)) + a.visitMiles * a.mileRate;
    const before = a.visitsBefore * perVisit;
    const after = a.visitsAfter * perVisit + a.toolCost;
    const scouting = before - after;
    const hasRoute = typeof routeMinutes === 'number' && Number.isFinite(routeMinutes) && routeMinutes >= 0;
    const crewTravel = a.paidTravel === true && hasRoute ?
      (a.baselineMinutes - routeMinutes) / 60 * 2 * a.crew * a.days * a.crewRate : null;
    return { before, after, perVisit, scouting, crewTravel, total: scouting + (crewTravel ?? 0),
      visitsAvoided: a.visitsBefore - a.visitsAfter };
  }
  const api = { estimate };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TypecastCosts = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
