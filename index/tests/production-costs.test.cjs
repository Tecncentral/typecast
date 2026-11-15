const test = require('node:test');
const assert = require('node:assert/strict');
const { estimate } = require('../production-costs.js');
const assumptions = () => ({ visitsBefore:10, visitsAfter:3, scouts:2, scoutRate:40, onsiteHours:2, travelHours:1,
  visitMiles:30, mileRate:0.7, toolCost:0, crew:20, days:3, crewRate:30, baselineMinutes:60, paidTravel:false });
test('editable scouting costs have an auditable before/after with tool costs deducted', () => {
  const a=assumptions(); a.toolCost=27;
  const r=estimate(a,null,true);
  assert.equal(r.perVisit,261); assert.equal(r.before,2610); assert.equal(r.after,810); assert.equal(r.total,1800);
});
test('paid travel counts two trips, people and shoot days, only with a route', () => {
  const a=assumptions(); a.paidTravel=true;
  assert.equal(estimate(a,30,true).crewTravel,1800);
  assert.equal(estimate(a,null,true).crewTravel,null);
  assert.equal(estimate(assumptions(),30,true).crewTravel,null);
});
test('longer commutes and extra scouting visits remain costs, not fabricated savings', () => {
  const a=assumptions(); a.visitsAfter=12; a.paidTravel=true;
  const r=estimate(a,90,true); assert.equal(r.scouting,-522); assert.equal(r.crewTravel,-1800); assert.equal(r.total,-2322);
});
test('partial/stale plans and invalid costs cannot display a savings claim', () => {
  assert.match(estimate(assumptions(),10,false).error,/complete plan/);
  for(const v of [NaN,Infinity,-1,'40']) { const a=assumptions(); a.scoutRate=v; assert.ok(estimate(a,10,true).error); }
});
test('sourced commercial day-rate example assumes days eliminated without double-counting hourly labor', () => {
  const a = {...assumptions(),billing:'daily',dailyRate:957.58,visitsBefore:5,visitsAfter:2,scouts:1,visitMiles:0};
  const r = estimate(a,null,true); assert.ok(Math.abs(r.scouting-2872.74)<0.00001);
  a.scoutRate=100000; a.onsiteHours=100; assert.equal(estimate(a,null,true).total,r.total);
});
