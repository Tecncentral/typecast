const test=require('node:test');
const assert=require('node:assert/strict');
const brief=require('../producer-brief.js');

function example() {
  return {version:1,project:{name:'Commercial pilot',reviewer:'Producer',decision:'Request owner confirmation',date:'2026-11-15'},
    plan:{mode:'live',current:true,fingerprint:'fnv1a:abc123',sceneCount:1,covered:1,locations:1,moves:0,propertyIds:['p1'],unknowns:['Filming access remains unknown'],constraintsSummary:'Three trucks; one-way route limit 45 minutes; source origin omitted',sceneAssignments:[{scene_id:'s1',heading:'INT. OFFICE',property_id:'p1',shot_id:'shot1'}]},
    budget:{assumptions:{billing:'daily',dailyRate:957.58,visitsBefore:5,visitsAfter:2,scouts:1,toolCost:0,scoutCommitment:'unconfirmed',sourceStatus:'published-reference',rateSource:'AICP / Local 399 commercial reference'},
      result:{modeledScenarioDelta:2872.74,cashPotential:null,knownCashDelta:0,laborCapacityValue:2872.74,scoutDaysReleased:3,scoutHoursReleased:null,cashUnresolved:['Billable commitment is unconfirmed'],projection:true,measured:false}},
    pilot:{baselineUnits:'',actualUnits:'',baselineCost:'',actualCost:'',source:'',notes:''}};
}

test('memo distinguishes projected capacity, unknown cash and producer-reported outcomes',()=>{
  const text=brief.renderText(example());
  assert.match(text,/Potential labor capacity value: \$2,872\.74/);
  assert.match(text,/Potential avoidable cash, after entered tool cost: Unknown/);
  assert.match(text,/Capacity value is not cash saved/);
  assert.match(text,/No causal savings or percentage reduction/);
  assert.match(text,/Filming permission.*unknown/);
  assert.match(text,/post-event data rights/);
  assert.doesNotMatch(text,/saved 60%|verified savings/i);
});

test('blank pilot data stays null and cannot silently become zero-valued evidence',()=>{
  const c=brief.normalizeCase(example());
  for(const k of ['baselineUnits','actualUnits','baselineCost','actualCost','source','notes']) assert.equal(c.pilot[k],null);
  assert.equal(c.budget.result.measured,false); assert.equal(c.budget.result.projection,true);
});

test('case snapshots are independent and deeply frozen',()=>{
  const raw=example(), c=brief.normalizeCase(raw);
  raw.plan.unknowns.push('later mutation'); raw.budget.assumptions.dailyRate=999;
  assert.equal(c.plan.unknowns.length,1); assert.equal(c.budget.assumptions.dailyRate,957.58);
  assert.ok(Object.isFrozen(c.budget.assumptions)); assert.ok(Object.isFrozen(c.plan.sceneAssignments[0]));
});

test('stale and imported cases cannot be rendered as current producer decisions',()=>{
  const c=example(); c.plan.current=false;
  assert.throws(()=>brief.renderHtml(c),/rebuild the current plan/);
  const loaded=brief.importCase(brief.exportJson(example()));
  assert.equal(loaded.plan.current,false);
  assert.throws(()=>brief.exportJson(loaded),/rebuild the current plan/);
});

test('only allowlisted inputs survive; homes, raw licensed rows, images and nested keys are omitted',()=>{
  const c=example(); c.api_key='sk-proj-THISISNOTAREALKEY123'; c.cache={raw:'LICENSED_ROW'};
  c.plan.lat=34.0522; c.plan.lon=-118.2437; c.plan.home={lat:1,lon:2};
  c.plan.sceneAssignments[0].image_path='/cache/private/foo.jpg';
  c.budget.assumptions.secret='SECRET'; c.pilot.receipt={url:'https://private'};
  const out=brief.exportJson(c);
  for(const secret of ['THISISNOTAREALKEY','LICENSED_ROW','34.0522','-118.2437','/cache/private','SECRET','https://private']) assert.ok(!out.includes(secret));
  assert.ok(out.includes('shot1'));
});

test('recognizable credentials in allowed text fields are rejected without echoing them',()=>{
  const c=example(); c.project.name='sk-proj-THISISNOTAREALKEY123';
  assert.throws(()=>brief.exportJson(c),err=>/credential-like/.test(err.message)&&!err.message.includes('THISISNOTAREALKEY'));
});

test('HTML text is escaped including project, constraint, financial source and pilot notes',()=>{
  const c=example(); const payload='<img src=x onerror="globalThis.POISON=1">';
  c.project.name=payload; c.plan.constraintsSummary=payload; c.budget.assumptions.sourceNote=payload; c.pilot.notes=payload;
  const html=brief.renderHtml(c);
  assert.ok(html.includes('&lt;img')); assert.ok(!html.includes('<img src=x')); assert.ok(!html.includes('<script'));
  assert.equal(globalThis.POISON,undefined);
});

test('bounded validation rejects nonfinite numbers, booleans, excessive lists and ambiguous billing',()=>{
  for(const value of [NaN,Infinity,-Infinity,true,'3']) { const c=example(); c.pilot.actualCost=value; assert.throws(()=>brief.normalizeCase(c),/finite number/); }
  const long=example(); long.plan.unknowns=Array(25).fill('x'); assert.throws(()=>brief.normalizeCase(long),/too many/);
  const bad=example(); bad.budget.assumptions.billing='weekly'; assert.throws(()=>brief.normalizeCase(bad),/billing/);
  const huge=example(); huge.pilot.notes='x'.repeat(1201); assert.throws(()=>brief.normalizeCase(huge),/too long/);
});

test('raw JSON constraints cannot be used as fingerprint and reveal an origin',()=>{
  const c=example(); c.plan.fingerprint='{"lat":34.0522,"lon":-118.2437}';
  assert.throws(()=>brief.normalizeCase(c),/opaque identifier/);
});

test('unknown keys and prototype-shaped JSON are dropped without prototype pollution',()=>{
  const c=example();
  c.budget.assumptions=JSON.parse('{"billing":"daily","dailyRate":957.58,"__proto__":{"polluted":true},"constructor":{"prototype":{"polluted":true}}}');
  const out=brief.exportJson(c);
  assert.ok(!out.includes('__proto__')); assert.ok(!out.includes('constructor')); assert.equal({}.polluted,undefined);
});

test('accessor fields are never evaluated',()=>{
  const c=example(); let touched=false;
  Object.defineProperty(c.project,'name',{get(){touched=true;return 'unsafe';}});
  assert.throws(()=>brief.normalizeCase(c),/accessor fields/); assert.equal(touched,false);
});

test('import size, format, date and measured-claim validation are explicit',()=>{
  assert.throws(()=>brief.importCase('{'),/invalid case JSON/);
  assert.throws(()=>brief.importCase(' '.repeat(100001)),/100 KB/);
  const c=example(); c.version=2; assert.throws(()=>brief.normalizeCase(c),/version/);
  c.version=1; c.project.date='yesterday'; assert.throws(()=>brief.normalizeCase(c),/ISO date/);
  c.project.date='2026-11-15'; c.budget.result.measured=true; assert.throws(()=>brief.normalizeCase(c),/cannot certify/);
});

test('negative cash and a real zero are preserved as conditional scenarios',()=>{
  const c=example(); c.budget.result.cashPotential=-100; c.budget.result.knownCashDelta=-100; c.budget.assumptions.toolCost=100;
  assert.match(brief.renderText(c),/Potential avoidable cash, after entered tool cost: -\$100/);
  c.budget.result.cashPotential=0; assert.match(brief.renderText(c),/Potential avoidable cash, after entered tool cost: \$0/);
});

test('memo carries reproducible travel and avoidability assumptions without an origin coordinate',()=>{
  const c=example();
  Object.assign(c.budget.assumptions,{paidTravel:true,crew:20,days:3,crewRate:30,baselineMinutes:60,routeMinutes:25,visitMiles:30,mileRate:.7,onsiteHours:2,travelHours:1,avoidableScoutUnits:1.5,hoursPerDay:10});
  const text=brief.renderText(c);
  assert.match(text,/Baseline \/ selected one-way minutes: 60 \/ 25/);
  assert.match(text,/Crew: 20; shoot days: 3/);
  assert.match(text,/vehicle miles: 30/);
  assert.match(text,/person-units cap: 1\.5/);
  c.budget.assumptions.routeMinutes=Infinity;
  assert.throws(()=>brief.normalizeCase(c),/routeMinutes.*finite number/);
});

test('invisible direction-control characters cannot make a memo print differently from its stored text',()=>{
  for (const ch of ['‮','⁦','⁩','\x7f']) {
    const c=example(); c.project.decision=`Approve ${ch}tcejer`;
    assert.throws(()=>brief.exportJson(c),/direction-control/);
    assert.throws(()=>brief.renderText(c),/direction-control/);
  }
  const ok=example(); ok.project.decision='Approve — café visit, 3 días';
  assert.doesNotThrow(()=>brief.exportJson(ok));
});
