/* Deterministic USD scenario arithmetic, shared by the UI and Node tests. */
(function (root) {
  'use strict';
  function estimate(a, routeMinutes = null, complete = false) {
    const keys = ['visitsBefore', 'visitsAfter', 'scouts', 'scoutRate', 'onsiteHours', 'travelHours', 'visitMiles', 'mileRate', 'toolCost', 'crew', 'days', 'crewRate', 'baselineMinutes'];
    if (!a || typeof a !== 'object' || keys.some(k => typeof a[k] !== 'number' || !Number.isFinite(a[k]) || a[k] < 0 || a[k] > 1000000))
      return { error: 'Enter a finite, non-negative value for every cost assumption.' };
    if (!complete) return { error: 'Build a complete plan before estimating its savings.' };
    if (a.billing != null && !['hourly', 'daily'].includes(a.billing))
      return { error: 'Choose hourly or daily scouting billing.' };
    if (a.billing === 'daily' && (typeof a.dailyRate !== 'number' || !Number.isFinite(a.dailyRate) || a.dailyRate < 0 || a.dailyRate > 1000000))
      return { error: 'Enter a valid billable daily scouting rate.' };
    const commitments = { scout: a.scoutCommitment ?? 'unconfirmed', crew: a.crewCommitment ?? 'unconfirmed', mileage: a.mileageCommitment ?? 'unconfirmed' };
    if (Object.values(commitments).some(v => !['unconfirmed', 'avoidable', 'committed'].includes(v)))
      return { error: 'Choose unconfirmed, avoidable or committed for each cost commitment.' };
    if (a.hoursPerDay != null && (typeof a.hoursPerDay !== 'number' || !Number.isFinite(a.hoursPerDay) || a.hoursPerDay <= 0 || a.hoursPerDay > 24))
      return { error: 'Hours per scouting day must be greater than zero and at most 24, or left unspecified.' };
    const visitsAvoided = a.visitsBefore - a.visitsAfter;
    // Day-rate units are person-days, hourly units are person-hours. Do not
    // manufacture an eight-hour day or turn guaranteed payroll into cash.
    const scoutUnits = visitsAvoided * a.scouts * (a.billing === 'daily' ? 1 : a.onsiteHours + a.travelHours);
    if (a.avoidableScoutUnits != null && (typeof a.avoidableScoutUnits !== 'number' || !Number.isFinite(a.avoidableScoutUnits)
        || a.avoidableScoutUnits < 0 || (scoutUnits > 0 && a.avoidableScoutUnits > scoutUnits)))
      return { error: 'Avoidable scouting units must be non-negative and cannot exceed the modeled positive person-days or person-hours released.' };
    const scoutUnitRate = a.billing === 'daily' ? a.dailyRate : a.scoutRate;
    const scoutLaborValue = scoutUnits * scoutUnitRate;
    const mileageValue = visitsAvoided * a.visitMiles * a.mileRate;
    const perVisit = (a.billing === 'daily' ? a.scouts * a.dailyRate : a.scouts * a.scoutRate * (a.onsiteHours + a.travelHours)) + a.visitMiles * a.mileRate;
    const before = a.visitsBefore * perVisit;
    const after = a.visitsAfter * perVisit + a.toolCost;
    const scouting = before - after;
    const hasRoute = typeof routeMinutes === 'number' && Number.isFinite(routeMinutes) && routeMinutes >= 0;
    const crewHoursReleased = a.paidTravel === true && hasRoute ?
      (a.baselineMinutes - routeMinutes) / 60 * 2 * a.crew * a.days : null;
    const crewTravel = crewHoursReleased == null ? null : crewHoursReleased * a.crewRate;
    const cashUnresolved = [];
    let knownCashDelta = 0 - a.toolCost;
    const cashPart = (value, commitment, label) => {
      if (value === 0) return;
      if (commitment === 'unconfirmed') cashUnresolved.push(`${label} commitment is unconfirmed; its modeled value is not cash savings.`);
      else if (commitment === 'avoidable') knownCashDelta += value;
      // Committed / guaranteed / salaried labor and fixed vehicle costs are
      // already payable. Their released capacity is reported separately.
    };
    const avoidableScoutUnitsApplied = scoutUnits > 0 ? (a.avoidableScoutUnits ?? scoutUnits) : null;
    // A positive cap can limit a weekly guarantee's cancellable portion. It
    // must never hide the signed cost of additional work in an avoidable model.
    const scoutCashValue = scoutUnits > 0 ? avoidableScoutUnitsApplied * scoutUnitRate : scoutLaborValue;
    cashPart(commitments.scout === 'unconfirmed' ? scoutLaborValue : scoutCashValue, commitments.scout, 'Scouting labor');
    cashPart(mileageValue, commitments.mileage, 'Vehicle costs');
    if (crewTravel != null) cashPart(crewTravel, commitments.crew, 'Crew travel labor');
    else if (a.paidTravel === true && a.crew > 0 && a.days > 0 && a.crewRate > 0)
      cashUnresolved.push('Requested crew travel has no known route; no complete combined cash projection is available.');
    const modeledScenarioDelta = scouting + (crewTravel ?? 0);
    return { before, after, perVisit, scouting, crewTravel, total: modeledScenarioDelta,
      visitsAvoided, modeledScenarioDelta, cashPotential: cashUnresolved.length ? null : knownCashDelta,
      knownCashDelta, cashUnresolved, laborCapacityValue: scoutLaborValue + (crewTravel ?? 0),
      scoutHoursReleased: a.billing === 'daily' ? (a.hoursPerDay == null ? null : scoutUnits * a.hoursPerDay) : scoutUnits,
      scoutDaysReleased: a.billing === 'daily' ? scoutUnits : null,
      crewHoursReleased, scoutLaborValue, mileageValue, crewLaborValue: crewTravel,
      avoidableScoutUnitsApplied: commitments.scout === 'avoidable' ? avoidableScoutUnitsApplied : null,
      commitments, projection: true, measured: false };
  }
  const api = { estimate };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TypecastCosts = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
