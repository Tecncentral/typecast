const test = require('node:test');
const assert = require('node:assert/strict');
const impact = require('../director-impact.js');
const lvs = require('../location-vs-set.js');

const cand = (pid, commute, shot = 'shot-' + pid) => ({ shot: { shot_id: shot, property_id: pid }, commute });
const est = (minutes, miles = null) => ({ status: 'estimated', minutes, miles });
const response = (limit, mode = 'live') => ({ mode, commute_limit_minutes: limit, scenes: [
  { id: 's1', heading: 'INT. KITCHEN - DAY', candidates: [cand('A', est(12.4, 6.3)), cand('A', est(12.4, 6.3), 'shot-A2'), cand('B', est(48)), cand('C', { status: 'unknown', minutes: null })] },
  { id: 's2', heading: 'INT. OFFICE - DAY', candidates: [cand('A', est(12.4, 6.3)), cand('D', est(19)), cand('E', null)] }] });
const picks = [{ scene_id: 's1', shot_id: 'shot-A', property_id: 'A' }, { scene_id: 's2', shot_id: 'shot-D', property_id: 'D' }];

test('drive summary counts properties once and separates too-far from unknown routes', () => {
  const d = impact.driveSummary(response(20), picks);
  assert.deepEqual([d.total, d.within, d.tooFar, d.unknown], [5, 2, 1, 2]);
  assert.equal(d.slowestSelected, 19);
  assert.deepEqual(d.selected.map(x => [x.heading, x.minutes, x.miles]), [['INT. KITCHEN - DAY', 12.4, 6.3], ['INT. OFFICE - DAY', 19, null]]);
  const text = impact.driveText(d);
  assert.equal(text.headline, '2 of 5 within 20 min');
  assert.match(text.sub, /3 excluded \(1 too far, 2 with no known route\)/);
  assert.match(text.sub, /no live traffic/);
});

test('a wider limit visibly admits more properties', () => {
  assert.equal(impact.driveText(impact.driveSummary(response(60), picks)).headline, '3 of 5 within 60 min');
});

test('with the filter off nothing is described as within or excluded', () => {
  const d = impact.driveSummary(response(null), picks);
  assert.equal(d.within, null);
  const text = impact.driveText(d);
  assert.equal(text.headline, 'Filter off');
  assert.doesNotMatch(text.sub, /excluded/);
});

test('unknown selected routes are stated, never shown as zero minutes, and mock plans say routing was not called', () => {
  const d = impact.driveSummary(response(30, 'mock'), [{ scene_id: 's2', shot_id: 'shot-E', property_id: 'E' }]);
  assert.equal(d.selected[0].minutes, null);
  assert.equal(d.slowestSelected, null);
  assert.match(impact.driveText(d).sub, /MOCK fixtures/);
  assert.equal(impact.driveSummary(null, picks), null);
  assert.equal(impact.driveText(null).headline, 'Set a base');
});

test('scouting tile shows the scenario value and never calls it a saving', () => {
  const result = { laborCapacityValue: 2872.74, scoutDaysReleased: 3, scoutHoursReleased: null, cashPotential: null };
  const text = impact.scoutText({ result, assumptions: { billing: 'daily', dailyRate: 957.58 } }, lvs.money);
  assert.equal(text.headline, '$2,872.74');
  assert.match(text.sub, /3 scout days at \$957\.58 per day/);
  assert.match(text.sub, /SCENARIO/);
  assert.match(text.sub, /Cash impact unconfirmed/);
  assert.doesNotMatch(text.sub, /\bsaves\b|\bsaved\b/i);
  const added = impact.scoutText({ result: { laborCapacityValue: -400, scoutHoursReleased: -10, cashPotential: -400 }, assumptions: { billing: 'hourly', scoutRate: 40 } }, lvs.money);
  assert.equal(added.headline, '−$400');
  assert.match(added.sub, /Added labor value/);
  assert.match(added.sub, /additional cash cost/);
  assert.equal(impact.scoutText({ result: { error: 'Build a complete plan before estimating its savings.' } }, lvs.money).headline, '—');
});

test('location-vs-set tile states a lower bound when materials are unknown', () => {
  const text = impact.setText(lvs.compare({ ...lvs.DEFAULTS }), lvs);
  assert.equal(text.headline, '≥ $29,881.44 less');
  assert.match(text.sub, /Real location \$2,220 · standing set \$2,000 · build ≥ \$32,101\.44/);
  const known = impact.setText(lvs.compare({ ...lvs.DEFAULTS, materials: 0 }), lvs);
  assert.equal(known.headline, '$29,881.44 less');
  assert.equal(impact.setText(lvs.compare({}), lvs).headline, '—');
});

test('selected locations list each property once with its scene count', () => {
  const same = [{ scene_id: 's1', shot_id: 'shot-A', property_id: 'A' }, { scene_id: 's2', shot_id: 'shot-A', property_id: 'A' }];
  const rows = impact.selectedLocations(impact.driveSummary(response(20), same));
  assert.deepEqual(rows, [{ propertyId: 'A', scenes: 2, minutes: 12.4, miles: 6.3 }]);
  assert.deepEqual(impact.selectedLocations(null), []);
});
