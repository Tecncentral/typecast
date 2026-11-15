'use strict';
// Decision-logic regressions for the producer workflow, run against the REAL director-planning.js in a fake DOM.
// Synthetic: the plan snapshot is supplied by each test; no browser, network or provider is used.
const test = require('node:test'), assert = require('node:assert/strict');
const { load, goodSnapshot, deferred } = require('./planning-harness.cjs');
const Brief = require('../producer-brief.js');
const KEY = 'typecast-producer-budget-v1';
const text = h => h.costs().join('\n');
const exportable = h => !h.nodes.exportProducerHtml.disabled && !h.nodes.exportProducerJson.disabled;

async function exported(h, id = 'exportProducerJson') { h.downloads.length = 0; await h.nodes[id].fire('click'); return h.downloads.length ? h.downloads[0].parts[0] : null; }
function caseJson(over = {}, drop = []) {
  const a = { visitsBefore: 4, visitsAfter: 1, scouts: 1, scoutRate: 40, onsiteHours: 2, travelHours: 1, visitMiles: 0, mileRate: 0.7, toolCost: 0, crew: 5, days: 2, crewRate: 30, baselineMinutes: 45,
    dailyRate: 957.58, billing: 'daily', paidTravel: false, scoutCommitment: 'avoidable', crewCommitment: 'unconfirmed', mileageCommitment: 'unconfirmed', sourceStatus: 'assumption', ...over };
  for (const k of drop) delete a[k];
  return JSON.stringify({ version: 1, project: { name: 'Imported', reviewer: 'R', decision: 'Approved kitchen' }, plan: { mode: 'live', sceneCount: 1, covered: 1, fingerprint: 'plan:abc' },
    budget: { assumptions: a, result: {} }, pilot: {} });
}

test('complete plan exports; unknown commitments stay unknown, not cash', async () => {
  const h = await load();
  assert.ok(exportable(h));
  assert.match(text(h), /Cash impact: unconfirmed/);
  const json = JSON.parse(await exported(h));
  assert.equal(json.budget.result.cashPotential, null);
  assert.equal(json.budget.result.measured, false);
});

test('a stale or incomplete plan can never be exported, and a later render does not resurrect it', async () => {
  const h = await load();
  assert.ok(await exported(h));
  h.snapshot(goodSnapshot({ stale: true }));
  await h.input('cost_toolCost', 1);
  assert.equal(h.nodes.exportProducerJson.disabled, true);
  assert.equal(await exported(h), null, 'click must not re-export the previously bound case');
  h.snapshot(goodSnapshot({ plan: { uncovered_scene_ids: ['s1'], property_ids: [] } }));
  assert.equal(await exported(h, 'exportProducerHtml'), null);
});

test('blank day rate in hourly mode is a legitimate unknown and must not block the export with a validation crash', async () => {
  const h = await load();
  await h.input('dailyScoutRate', '');
  assert.ok(exportable(h), h.nodes.producerCaseStatus.textContent);
  const json = JSON.parse(await exported(h));
  assert.equal(json.budget.assumptions.dailyRate, null);
});

test('blank day rate in day-rate mode refuses to estimate', async () => {
  const h = await load();
  h.nodes.scoutBilling.value = 'daily'; await h.input('dailyScoutRate', '');
  assert.equal(h.nodes.exportProducerJson.disabled, true);
  assert.match(text(h), /daily scouting rate/);
});

test('the sourced $957.58 day rate is shown exactly, not rounded to $958', async () => {
  const h = await load();
  await h.nodes.commercialRatePreset.fire('click');
  assert.match(text(h), /\$957\.58\/day/);
  assert.doesNotMatch(text(h), /\$958\b/);
});

test('guaranteed salary releases capacity but no labor cash; avoidable day rate yields cash', async () => {
  const h = await load();
  await h.nodes.commercialRatePreset.fire('click');           // 5 -> 2 days, one scout, unconfirmed commitments
  assert.match(text(h), /Cash impact: unconfirmed/);
  h.nodes.scoutCommitment.value = 'committed'; h.nodes.mileageCommitment.value = 'committed'; await h.nodes.scoutCommitment.fire('input');
  assert.match(text(h), /\$0 potential cash avoided/);
  assert.match(text(h), /Labor capacity value: \$2,872\.74/);
  h.nodes.scoutCommitment.value = 'avoidable'; await h.nodes.scoutCommitment.fire('input');
  assert.match(text(h), /\$2,872\.74 potential cash avoided/);
  h.nodes.avoidableScoutUnits.value = '1'; await h.nodes.avoidableScoutUnits.fire('input');
  assert.match(text(h), /\$957\.58 potential cash avoided/);
});

test('more visits after Typecast than before is stated as added cost, never as "-N fewer"', async () => {
  const h = await load();
  await h.nodes.commercialRatePreset.fire('click');
  h.nodes.scoutCommitment.value = 'avoidable'; h.nodes.mileageCommitment.value = 'avoidable';
  await h.input('cost_visitsAfter', 7);
  const t = text(h);
  assert.doesNotMatch(t, /-\d+ fewer/);
  assert.doesNotMatch(t, /-\d+(\.\d+)? scout person-days potentially released/);
  assert.match(t, /additional/i);
  assert.match(t, /additional cash cost/);
});

// ---- storage opt-in / clear are literal ----
test('opt-in writes only after consent; clear removes the key and later edits do not recreate it', async () => {
  const h = await load();
  await h.input('cost_crew', 9);
  assert.equal(h.store.has(KEY), false);
  h.nodes.keepProducerCase.checked = true; await h.nodes.keepProducerCase.fire('change');
  assert.equal(JSON.parse(h.store.get(KEY)).fields.cost_crew, '9');
  await h.nodes.clearProducerCase.fire('click');
  assert.equal(h.store.has(KEY), false); assert.equal(h.nodes.keepProducerCase.checked, false);
  await h.input('cost_crew', 11);
  assert.equal(h.store.has(KEY), false, 'an edit after Clear must not silently re-store');
});

test('opt-in does not claim storage when the browser refuses the write', async () => {
  const h = await load({ failStorage: { set: true } });
  h.nodes.keepProducerCase.checked = true; await h.nodes.keepProducerCase.fire('change');
  assert.equal(h.nodes.keepProducerCase.checked, false, 'checkbox must not claim persistence that did not happen');
  assert.doesNotMatch(h.nodes.producerCaseStatus.textContent, /is stored in this browser/);
  assert.match(h.nodes.producerCaseStatus.textContent, /unavailable|not saved/i);
});

test('clear does not claim removal when the browser refuses the delete', async () => {
  const h = await load({ storage: { [KEY]: JSON.stringify({ version: 1, fields: { cost_crew: '4' }, paidTravel: false }) }, failStorage: { remove: true } });
  assert.equal(h.nodes.keepProducerCase.checked, true);
  await h.nodes.clearProducerCase.fire('click');
  assert.doesNotMatch(h.nodes.producerCaseStatus.textContent, /^Stored budget case cleared/);
  assert.match(h.nodes.producerCaseStatus.textContent, /could not|not cleared|still/i);
  assert.equal(h.nodes.keepProducerCase.checked, false, 'no further writes after an opt-out attempt');
});

test('stored case restores inputs but never an export: a plan is still required', async () => {
  const h = await load({ storage: { [KEY]: JSON.stringify({ version: 1, fields: { cost_crew: '4', producerDecision: 'Approve it' }, paidTravel: false }) } });
  assert.equal(h.nodes.cost_crew.value, '4');
  assert.match(h.nodes.producerCaseStatus.textContent, /Build a current plan/);
});

// ---- import races ----
test('import: a late file read cannot overwrite inputs the producer changed meanwhile (checkbox included)', async () => {
  const h = await load(); const d = deferred();
  const pending = h.nodes.importProducerJson.fire('change', { target: { files: [{ size: 10, text: () => d.promise }], value: 'x' } });
  h.nodes.paidTravel.checked = true; await h.nodes.paidTravel.fire('change');
  d.resolve(caseJson()); await pending;
  assert.equal(h.nodes.paidTravel.checked, true, 'user choice was overwritten by a late import');
  assert.match(h.nodes.producerCaseStatus.textContent, /retained/);
  assert.equal(h.nodes.producerName.value, '');
});

test('import: the later-selected file wins even if the earlier read finishes last', async () => {
  const h = await load(); const slow = deferred(), fast = deferred();
  const a = h.nodes.importProducerJson.fire('change', { target: { files: [{ size: 10, text: () => slow.promise }], value: 'x' } });
  const b = h.nodes.importProducerJson.fire('change', { target: { files: [{ size: 10, text: () => fast.promise }], value: 'x' } });
  fast.resolve(caseJson({ crew: 11 }).replace('Imported', 'SecondFile')); await b;
  slow.resolve(caseJson({ crew: 12 }).replace('Imported', 'FirstFile')); await a;
  assert.equal(h.nodes.producerName.value, 'SecondFile');
  assert.equal(h.nodes.cost_crew.value, '11');
});

test('import: a case missing a field becomes unknown instead of mixing in the previous project', async () => {
  const h = await load();
  await h.input('cost_crew', 7); await h.input('cost_visitsBefore', 99); await h.input('avoidableScoutUnits', 3);
  h.nodes.costSourceNote.value = 'old project quote'; h.nodes.producerReviewer.value = 'Old reviewer';
  await h.nodes.importProducerJson.fire('change', { target: { files: [h.file(caseJson({}, ['crew', 'visitsBefore', 'avoidableScoutUnits', 'rateSource']))], value: 'x' } });
  assert.equal(h.nodes.cost_crew.value, '', 'previous project crew count leaked into the imported budget');
  assert.equal(h.nodes.cost_visitsBefore.value, '', 'a missing value is unknown, not an invented default');
  assert.equal(h.nodes.exportProducerJson.disabled, true);
  assert.equal(h.nodes.avoidableScoutUnits.value, '');
  assert.equal(h.nodes.costSourceNote.value, '');
});

test('import restores assumptions only and requires a rebuild before any export', async () => {
  const h = await load();
  await h.nodes.importProducerJson.fire('change', { target: { files: [h.file(caseJson())], value: 'x' } });
  assert.equal(h.nodes.exportProducerJson.disabled, true);
  assert.match(text(h), /Build a complete plan/);
  const next = goodSnapshot(); h.snapshot(next); await h.input('cost_toolCost', 0);
  assert.ok(exportable(h), 'a freshly built plan object releases the gate');
});

test('import: oversize, malformed and measured-savings files are refused and change nothing', async () => {
  const h = await load(); await h.input('cost_crew', 7);
  for (const f of [h.file('x', 100001), h.file('{nope'), h.file(JSON.stringify({ ...JSON.parse(caseJson()), budget: { assumptions: {}, result: { measured: true } } }))]) {
    await h.nodes.importProducerJson.fire('change', { target: { files: [f], value: 'x' } });
    assert.match(h.nodes.producerCaseStatus.textContent, /Could not restore/);
    assert.equal(h.nodes.cost_crew.value, '7');
  }
});

// ---- decision text is bound to a plan ----
test('a decision written for one plan is flagged when exported against a different plan', async () => {
  const h = await load();
  await h.input('producerDecision', 'Shortlist the Maple Street kitchen');
  const first = JSON.parse(await exported(h));
  assert.equal(first.plan.unknowns.some(u => /decision.*(earlier|another|not bound|different)/i.test(u)), false);
  const s2 = goodSnapshot({ assignments: [{ scene_id: 's1', shot_id: 'shot-P2', property_id: 'P2' }], plan: { uncovered_scene_ids: [], locations: 1, company_moves: 0, property_ids: ['P2'] } });
  s2.response.scenes[0].candidates = [{ eligible: true, shot: { shot_id: 'shot-P2', property_id: 'P2' }, warnings: [] }];
  h.snapshot(s2); await h.input('cost_toolCost', 0);
  const second = JSON.parse(await exported(h));
  assert.notEqual(second.plan.fingerprint, first.plan.fingerprint);
  assert.ok(second.plan.unknowns.some(u => /decision.*(earlier|another|different)/i.test(u)), JSON.stringify(second.plan.unknowns));
});

test('a decision restored from a file is flagged as unbound until the producer re-enters it', async () => {
  const h = await load();
  await h.nodes.importProducerJson.fire('change', { target: { files: [h.file(caseJson())], value: 'x' } });
  h.snapshot(goodSnapshot()); await h.input('cost_toolCost', 0);
  const j = JSON.parse(await exported(h));
  assert.ok(j.plan.unknowns.some(u => /decision.*(restored|file|not bound|another)/i.test(u)), JSON.stringify(j.plan.unknowns));
  await h.input('producerDecision', 'Re-confirmed for this plan');
  const k = JSON.parse(await exported(h));
  assert.equal(k.plan.unknowns.some(u => /Reviewer decision/i.test(u)), false);
});

// ---- exporter safety ----
test('exporter refuses provider keys, bearer tokens, URL credentials and private keys in free text', () => {
  const bad = ['sk-ant-abcdefghijklmnop123456', 'AIzaSyA1234567890abcdefghijklmnopqrstuv', 'ghp_abcdefghijklmnopqrstuvwxyz0123456789', 'AKIAABCDEFGHIJKLMNOP',
    'Authorization: Bearer abcdefghijklmnop123456', 'https://user:hunter2@example.com/quote', '-----BEGIN PRIVATE KEY-----', 'password=hunter2', 'https://x.test/a?api_key=abc'];
  for (const note of bad) {
    const c = JSON.parse(caseJson()); c.plan.current = true; c.budget.assumptions.rateSource = note;
    assert.throws(() => Brief.normalizeCase(c), /credential-like/, note);
  }
  const ok = JSON.parse(caseJson()); ok.plan.current = true; ok.budget.assumptions.rateSource = 'Quote from vendor, 2026-11-01; password policy discussed';
  assert.doesNotThrow(() => Brief.normalizeCase(ok));
});

test('memo HTML escapes every producer-entered string', async () => {
  const h = await load();
  await h.input('producerName', '<img src=x onerror=alert(1)>'); await h.input('producerDecision', '"><script>x</script>');
  const html = await exported(h, 'exportProducerHtml');
  assert.doesNotMatch(html, /<img src=x|<script>x/);
  assert.match(html, /&lt;img src=x/);
});

test('mock plans are labeled mock in the memo, JSON and screen', async () => {
  const s = goodSnapshot(); s.response.mode = 'mock'; const h = await load({ snapshot: s });
  assert.match(text(h), /MOCK PLAN/);
  assert.equal(JSON.parse(await exported(h)).plan.mode, 'mock');
  assert.match(await exported(h, 'exportProducerHtml'), /MOCK SOURCE MODE/);
});

test('community mode and a partly covered plan never produce a decision memo', async () => {
  const h = await load({ snapshot: goodSnapshot({ mode: 'community' }) });
  assert.equal(h.nodes.exportProducerJson.disabled, true);
  const g = await load({ snapshot: goodSnapshot({ assignments: [], sceneCount: 1 }) });
  assert.equal(g.nodes.exportProducerHtml.disabled, true);
});
