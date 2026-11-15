/* Found location vs standing set vs building a set: deterministic USD scenario arithmetic.
   Shared by the Director UI and Node tests. Every default carries its published source;
   crew size and build days are the producer's own assumptions and are labelled as such.
   Results are scenarios, never measured savings. */
(function (root) {
  'use strict';
  const SOURCES = {
    locationHourly: { label: 'Giggster: average Los Angeles filming location, $222 per hour (listed prices)',
      url: 'https://giggster.com/find/los-angeles--ca/filming', checked: '2026-11-15', kind: 'published listing average' },
    standingShootDay: { label: 'Affordable Sound Stages (Los Angeles): living room, kitchen or bedroom standing set, $2,000 per 12-hour shoot day, $1,000 per prep or strike day',
      url: 'https://affordablesoundstages.com/standing-sets/', checked: '2026-11-15', kind: 'published vendor price' },
    stageDay: { label: 'Tools for Film glossary: a 10,000 sq ft Los Angeles stage runs $3,000 to $7,000 per day, without lighting, grip or set construction (low end used)',
      url: 'https://www.toolsforfilm.com/glossary/soundstage', checked: '2026-11-15', kind: 'published trade guide' },
    crewHourly: { label: 'IATSE / AICP commercial agreement 2025-2028, Los Angeles County: Propmaker $57.82 per hour (minimum; no fringes or overtime)',
      url: 'https://www.iatse728.org/system/files/2025-10/2025-2028-iatse-aicp-commerical-production-agreement-%5Bwage-charts%5D.pdf', checked: '2026-11-15', kind: 'union wage chart' },
  };
  const DEFAULTS = {
    shootDays: 1,
    locationHourly: 222, locationHoursPerDay: 10, locationPrepDays: 0,
    standingShootDay: 2000, standingPrepDay: 1000, standingPrepDays: 0,
    stageDay: 3000, buildDays: 5, strikeDays: 1, buildCrew: 4, crewHourly: 57.82, crewHoursPerDay: 8,
    materials: null,
  };
  const LIMIT = 100000000;
  const NUMERIC = ['shootDays', 'locationHourly', 'locationHoursPerDay', 'locationPrepDays', 'standingShootDay',
    'standingPrepDay', 'standingPrepDays', 'stageDay', 'buildDays', 'strikeDays', 'buildCrew', 'crewHourly', 'crewHoursPerDay'];
  const finite = v => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= LIMIT;
  const cents = n => Math.round(n * 100) / 100;

  function compare(input) {
    if (!input || typeof input !== 'object') return { error: 'Enter the location and set assumptions.' };
    const a = {};
    for (const k of NUMERIC) {
      a[k] = input[k];
      if (!finite(a[k])) return { error: 'Enter a finite, non-negative value for every location and set assumption.' };
    }
    if (a.shootDays < 1 || !Number.isInteger(a.shootDays) || a.shootDays > 365) return { error: 'Shoot days must be a whole number from 1 to 365.' };
    if (a.locationHoursPerDay > 24 || a.crewHoursPerDay > 24) return { error: 'Hours per day cannot exceed 24.' };
    // Blank materials are unknown, not zero: the build total then becomes a lower bound.
    const materials = input.materials == null ? null : input.materials;
    if (materials !== null && !finite(materials)) return { error: 'Materials must be a finite, non-negative amount or left blank.' };
    const lease = input.leaseFloorPerDay == null ? null : input.leaseFloorPerDay;
    if (lease !== null && !finite(lease)) return { error: 'Lease reference must be a finite, non-negative amount or omitted.' };

    const locationPerDay = a.locationHourly * a.locationHoursPerDay;
    const location = cents(locationPerDay * (a.shootDays + a.locationPrepDays));
    const standing = cents(a.standingShootDay * a.shootDays + a.standingPrepDay * a.standingPrepDays);
    const stageDays = a.buildDays + a.shootDays + a.strikeDays;
    const stage = a.stageDay * stageDays;
    const labor = a.buildCrew * a.crewHourly * a.crewHoursPerDay * (a.buildDays + a.strikeDays);
    const build = cents(stage + labor + (materials ?? 0));
    const buildIsLowerBound = materials === null;

    const options = [
      { key: 'location', label: 'Real found location', total: location },
      { key: 'standing', label: 'Rented standing set', total: standing },
      { key: 'build', label: 'Build a set on a stage', total: build, lowerBound: buildIsLowerBound },
    ];
    const cheapest = options.reduce((best, o) => (o.total < best.total ? o : best));
    const tie = options.filter(o => o.total === cheapest.total).length > 1;

    // Shoot days at which building stops costing more than the location, holding everything else fixed.
    const buildFixed = a.stageDay * (a.buildDays + a.strikeDays) + labor + (materials ?? 0) - locationPerDay * a.locationPrepDays;
    let breakEvenShootDays = null;
    if (locationPerDay > a.stageDay && buildFixed > 0) breakEvenShootDays = Math.ceil(buildFixed / (locationPerDay - a.stageDay));
    else if (buildFixed <= 0) breakEvenShootDays = 0;

    return {
      assumptions: { ...a, materials, leaseFloorPerDay: lease },
      location, standing, build, buildIsLowerBound,
      parts: { locationPerDay: cents(locationPerDay), stage: cents(stage), stageDays, labor: cents(labor), materials },
      locationVsBuild: cents(build - location), locationVsStanding: cents(standing - location),
      cheapest: tie ? null : cheapest.key, breakEvenShootDays,
      leaseFloorTotal: lease === null ? null : cents(lease * (a.shootDays + a.locationPrepDays)),
      projection: true, measured: false,
    };
  }

  const money = n => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(n);

  /* One sentence a producer can read aloud. Never says "saves": the inputs are assumptions. */
  function verdict(r) {
    if (!r || r.error) return r?.error || '';
    const days = `${r.assumptions.shootDays} shoot day${r.assumptions.shootDays === 1 ? '' : 's'}`;
    const atLeast = r.buildIsLowerBound ? 'at least ' : '';
    const build = r.locationVsBuild > 0 ? `${atLeast}${money(r.locationVsBuild)} less than building a set`
      : r.locationVsBuild < 0 ? `${money(-r.locationVsBuild)} more than building a set${r.buildIsLowerBound ? ' before materials' : ''}`
      : 'the same as building a set';
    const standing = r.locationVsStanding > 0 ? `${money(r.locationVsStanding)} less than a rented standing set`
      : r.locationVsStanding < 0 ? `${money(-r.locationVsStanding)} more than a rented standing set`
      : 'the same as a rented standing set';
    return `At these inputs, ${days} at the real location would cost ${build} and ${standing}.`;
  }

  const api = { compare, verdict, DEFAULTS, SOURCES, money };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TypecastLocationVsSet = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
