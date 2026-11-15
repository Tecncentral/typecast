const test = require('node:test');
const assert = require('node:assert/strict');
const lvs = require('../location-vs-set.js');

const base = () => ({ ...lvs.DEFAULTS });

test('defaults reproduce the published-rate arithmetic exactly', () => {
  const r = lvs.compare(base());
  assert.equal(r.location, 2220);                       // $222/h x 10 h x 1 day
  assert.equal(r.standing, 2000);                       // $2,000 per shoot day
  assert.equal(r.parts.stage, 21000);                   // $3,000 x (5 build + 1 shoot + 1 strike)
  assert.equal(r.parts.labor, 11101.44);                // 4 x $57.82 x 8 h x 6 days
  assert.equal(r.build, 32101.44);
  assert.equal(r.locationVsBuild, 29881.44);
  assert.equal(r.locationVsStanding, -220);
  assert.equal(r.cheapest, 'standing');
  assert.equal(r.projection, true);
  assert.equal(r.measured, false);
});

test('blank materials make the build total a lower bound; entered materials are added', () => {
  assert.equal(lvs.compare(base()).buildIsLowerBound, true);
  const withMaterials = lvs.compare({ ...base(), materials: 15000 });
  assert.equal(withMaterials.buildIsLowerBound, false);
  assert.equal(withMaterials.build, 47101.44);
  assert.match(lvs.verdict(lvs.compare(base())), /at least \$29,881\.44 less than building a set/);
  assert.doesNotMatch(lvs.verdict(withMaterials), /at least/);
});

test('a real zero for materials is a known zero, not unknown', () => {
  const r = lvs.compare({ ...base(), materials: 0 });
  assert.equal(r.buildIsLowerBound, false);
  assert.equal(r.build, 32101.44);
});

test('a long shoot can make the built set cheaper, and the verdict says so instead of claiming savings', () => {
  const r = lvs.compare({ ...base(), locationHourly: 600, shootDays: 30, materials: 0 });
  assert.equal(r.location, 180000);
  assert.equal(r.build, 3000 * 36 + 11101.44);
  assert.ok(r.locationVsBuild < 0);
  assert.equal(r.cheapest, 'standing');
  assert.match(lvs.verdict(r), /more than building a set/);
  assert.doesNotMatch(lvs.verdict(r), /\bsaves?\b/i);
});

test('break-even shoot days exist only when the location costs more per day than the stage', () => {
  assert.equal(lvs.compare(base()).breakEvenShootDays, null);        // $2,220/day < $3,000/day stage: never
  const r = lvs.compare({ ...base(), locationHourly: 500, materials: 0 });
  // fixed build cost 18,000 + 11,101.44 = 29,101.44; daily gap 5,000 - 3,000 = 2,000 -> 15 days
  assert.equal(r.breakEvenShootDays, 15);
  const at15 = lvs.compare({ ...base(), locationHourly: 500, materials: 0, shootDays: 15 });
  const at14 = lvs.compare({ ...base(), locationHourly: 500, materials: 0, shootDays: 14 });
  assert.ok(at15.locationVsBuild <= 0 && at14.locationVsBuild > 0);
});

test('prep days are charged for the location and the standing set', () => {
  const r = lvs.compare({ ...base(), locationPrepDays: 1, standingPrepDays: 2 });
  assert.equal(r.location, 4440);
  assert.equal(r.standing, 4000);
});

test('the CoStar lease floor is carried as a reference and never enters a total', () => {
  const without = lvs.compare(base());
  const withLease = lvs.compare({ ...base(), leaseFloorPerDay: 200, shootDays: 3 });
  assert.equal(withLease.leaseFloorTotal, 600);
  assert.equal(withLease.location, 2220 * 3);
  assert.equal(without.leaseFloorTotal, null);
});

test('invalid, negative, nonfinite and out-of-range inputs return an error, never a number', () => {
  for (const bad of [null, {}, { ...base(), shootDays: 0 }, { ...base(), shootDays: 1.5 }, { ...base(), shootDays: 400 },
    { ...base(), locationHourly: -1 }, { ...base(), stageDay: Infinity }, { ...base(), crewHourly: NaN },
    { ...base(), buildCrew: '4' }, { ...base(), locationHoursPerDay: 25 }, { ...base(), materials: -5 },
    { ...base(), materials: 'lots' }, { ...base(), leaseFloorPerDay: NaN }, { ...base(), stageDay: 1e12 }]) {
    const r = lvs.compare(bad);
    assert.ok(r.error, JSON.stringify(bad));
    assert.equal(r.location, undefined);
    assert.equal(lvs.verdict(r), r.error);
  }
});

test('equal totals report no single cheapest option', () => {
  const r = lvs.compare({ ...base(), locationHourly: 200 });       // $2,000 location = $2,000 standing set
  assert.equal(r.cheapest, null);
  assert.match(lvs.verdict(r), /the same as a rented standing set/);
});

test('every default has a published source with a URL and check date; assumptions without one are not listed as sourced', () => {
  for (const key of ['locationHourly', 'standingShootDay', 'stageDay', 'crewHourly']) {
    assert.match(lvs.SOURCES[key].url, /^https:\/\//);
    assert.equal(lvs.SOURCES[key].checked, '2026-11-15');
  }
  for (const key of ['buildDays', 'strikeDays', 'buildCrew', 'materials']) assert.equal(lvs.SOURCES[key], undefined);
});
