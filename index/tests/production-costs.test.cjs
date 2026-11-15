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

const daily = (extra = {}) => ({ ...assumptions(), billing:'daily', dailyRate:957.58,
  visitsBefore:5, visitsAfter:2, scouts:1, visitMiles:0, ...extra });
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 0.000001, `${actual} != ${expected}`);

test('a published rate and assumed days released do not establish avoidable cash by default', () => {
  const r=estimate(daily(),null,true);
  near(r.modeledScenarioDelta,2872.74); near(r.laborCapacityValue,2872.74);
  assert.equal(r.cashPotential,null); assert.equal(r.knownCashDelta,0);
  assert.equal(r.scoutDaysReleased,3); assert.equal(r.scoutHoursReleased,null);
  assert.equal(r.commitments.scout,'unconfirmed'); assert.equal(r.cashUnresolved.length,1);
  assert.equal(r.projection,true); assert.equal(r.measured,false);
});

test('committed or salaried labor releases modeled capacity but no payroll cash; tool costs remain payable', () => {
  const r=estimate(daily({scoutCommitment:'committed',toolCost:100}),null,true);
  near(r.laborCapacityValue,2872.74); assert.equal(r.cashPotential,-100);
  assert.equal(r.knownCashDelta,-100); assert.deepEqual(r.cashUnresolved,[]);
});

test('explicitly avoidable billable days can produce a net cash scenario after tool charges', () => {
  const r=estimate(daily({scoutCommitment:'avoidable',toolCost:100}),null,true);
  near(r.cashPotential,2772.74); near(r.knownCashDelta,2772.74);
  assert.equal(r.avoidableScoutUnitsApplied,3);
});

test('a weekly guarantee can cap the cancellable portion of released scout person-days', () => {
  const r=estimate(daily({scouts:2,scoutCommitment:'avoidable',avoidableScoutUnits:1.5}),null,true);
  assert.equal(r.scoutDaysReleased,6); assert.equal(r.avoidableScoutUnitsApplied,1.5);
  near(r.cashPotential,1436.37); near(r.laborCapacityValue,5745.48);
  assert.ok(estimate(daily({avoidableScoutUnits:4}),null,true).error);
});

test('hourly capacity counts people and time; daily hours require an explicit hours-per-day input', () => {
  const a={...assumptions(),scoutCommitment:'committed',mileageCommitment:'committed'};
  const r=estimate(a,null,true);
  assert.equal(r.scoutHoursReleased,42); assert.equal(r.scoutDaysReleased,null);
  near(r.laborCapacityValue,1680); assert.equal(r.cashPotential,0);
  assert.equal(estimate(daily({hoursPerDay:10}),null,true).scoutHoursReleased,30);
  for(const value of [0,25,NaN,true,'8']) assert.ok(estimate(daily({hoursPerDay:value}),null,true).error);
});

test('vehicle costs have their own avoidability treatment, independent of committed payroll', () => {
  const a={...assumptions(),scoutCommitment:'committed',mileageCommitment:'avoidable',toolCost:10};
  const r=estimate(a,null,true);
  assert.equal(r.mileageValue,147); assert.equal(r.cashPotential,137);
  a.mileageCommitment='committed'; assert.equal(estimate(a,null,true).cashPotential,-10);
  a.mileageCommitment='unconfirmed'; assert.equal(estimate(a,null,true).cashPotential,null);
});

test('known cash subtotal is retained while an unconfirmed component prevents a combined cash claim', () => {
  const r=estimate({...assumptions(),mileageCommitment:'avoidable',toolCost:20},null,true);
  assert.equal(r.cashPotential,null); assert.equal(r.knownCashDelta,127);
  assert.match(r.cashUnresolved.join(' '),/Scouting labor/);
});

test('crew travel has an independent payroll gate, including salary and missing routes', () => {
  const a=daily({scoutCommitment:'committed',paidTravel:true,crewCommitment:'committed'});
  let r=estimate(a,30,true);
  assert.equal(r.crewHoursReleased,60); assert.equal(r.crewLaborValue,1800);
  assert.equal(r.cashPotential,0);
  a.crewCommitment='avoidable'; assert.equal(estimate(a,30,true).cashPotential,1800);
  a.crewCommitment='unconfirmed'; assert.equal(estimate(a,30,true).cashPotential,null);
  a.crewCommitment='avoidable'; r=estimate(a,null,true);
  assert.equal(r.cashPotential,null); assert.equal(r.crewHoursReleased,null);
  assert.match(r.cashUnresolved.join(' '),/no known route/);
});

test('additional work and longer paid routes remain negative costs and cannot be capped away', () => {
  const a={...assumptions(),visitsAfter:12,paidTravel:true,scoutCommitment:'avoidable',mileageCommitment:'avoidable',crewCommitment:'avoidable',avoidableScoutUnits:0,toolCost:50};
  const r=estimate(a,90,true);
  assert.equal(r.scoutHoursReleased,-12); assert.equal(r.crewHoursReleased,-60);
  assert.equal(r.cashPotential,-2372); assert.equal(r.knownCashDelta,-2372);
  assert.equal(r.avoidableScoutUnitsApplied,null);
});

test('zero delta requires no avoidability assertion, but never converts a source label into a measured outcome', () => {
  const r=estimate(daily({visitsAfter:5,toolCost:25,costEvidence:'producer_quote',avoidableScoutUnits:0}),null,true);
  assert.equal(r.cashPotential,-25); assert.equal(r.laborCapacityValue,0);
  assert.equal(r.projection,true); assert.equal(r.measured,false);
  // A zero avoidable-units entry does not resolve an otherwise unknown commitment.
  assert.equal(estimate(daily({avoidableScoutUnits:0}),null,true).cashPotential,null);
});

test('bad commitment vocabulary, billing basis and nonfinite caps return validation errors', () => {
  for(const extra of [{scoutCommitment:'weekly'},{crewCommitment:true},{mileageCommitment:'variable'},{billing:'monthly'},
    {avoidableScoutUnits:-1},{avoidableScoutUnits:NaN},{avoidableScoutUnits:'2'},{avoidableScoutUnits:true}])
    assert.ok(estimate(daily(extra),30,true).error);
});
