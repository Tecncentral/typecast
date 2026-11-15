/* Allowlisted producer recce memo. Financial output is projected; outcomes are reported. */
(function (root) {
  'use strict';
  const MAX_BYTES = 100000;
  // Free-text fields end up in a file the producer may email. Refuse common secret shapes rather than export them.
  const CREDENTIAL = new RegExp([
    String.raw`\bsk-(?:proj-|ant-|live-|test-)?[a-z0-9_-]{12,}`, String.raw`\b(?:OPENAI|ANTHROPIC|VISION|LLM)_API_KEY\s*[:=]`,
    String.raw`[?&](?:api_?key|token|access_token)=`, String.raw`\bAIza[0-9A-Za-z_-]{30,}`, String.raw`\bgh[pousr]_[A-Za-z0-9]{20,}`,
    String.raw`\bAKIA[0-9A-Z]{16}\b`, String.raw`\bBearer\s+[A-Za-z0-9._~+/=-]{16,}`, '-----BEGIN [A-Z ]*PRIVATE KEY-----',
    String.raw`\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*\S{3,}`, String.raw`://[^/\s:@]+:[^/\s@]+@`].join('|'), 'i');
  const fail = message => { throw new Error(`Producer brief: ${message}`); };
  function object(value, name) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${name} must be an object`);
    return value;
  }
  function own(value, key) {
    if (!value || typeof value !== 'object') return undefined;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (descriptor && !('value' in descriptor)) fail('accessor fields are not supported');
    return descriptor?.value;
  }
  function string(value, max, name, nullable = true) {
    if ((value == null || value === '') && nullable) return null;
    if (typeof value !== 'string') fail(`${name} must be text`);
    const text = value.trim();
    if (!text && nullable) return null;
    if (!text || text.length > max || /[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text)) fail(`${name} is blank or too long`);
    // Bidi overrides/isolates and DEL can make a printed memo read differently from its stored text.
    if (/[\x7f‪-‮⁦-⁩]/.test(text)) fail(`${name} contains invisible direction-control characters`);
    if (CREDENTIAL.test(text)) fail('credential-like text is not exportable');
    return text;
  }
  function number(value, name, { nullable = true, min = -1e12, max = 1e12, integer = false } = {}) {
    if ((value == null || value === '') && nullable) return null;
    if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max || (integer && !Number.isInteger(value))) fail(`${name} must be a bounded finite number`);
    return value;
  }
  function list(value, max, name, transform) {
    if (value == null) return [];
    if (!Array.isArray(value) || value.length > max) fail(`${name} has too many items`);
    return value.map(transform);
  }
  function identifier(value, max, name, nullable = true) {
    const text = string(value, max, name, nullable);
    if (text !== null && !/^[A-Za-z0-9_.:-]+$/.test(text)) fail(`${name} must be an opaque identifier`);
    return text;
  }
  function commitment(value) {
    if (value == null || value === '') return 'unconfirmed';
    if (!['unconfirmed', 'avoidable', 'committed'].includes(value)) fail('unknown cost commitment');
    return value;
  }
  function freeze(value) {
    if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
    return value;
  }
  function normalize(input, requireCurrent) {
    object(input, 'case');
    if (own(input, 'version') !== 1) fail('unsupported case version');
    const project = object(own(input, 'project') || {}, 'project');
    const plan = object(own(input, 'plan'), 'plan');
    if (requireCurrent && own(plan, 'current') !== true) fail('rebuild the current plan before exporting a decision');
    const mode = own(plan, 'mode');
    if (!['mock', 'live', 'unknown'].includes(mode)) fail('invalid source mode');
    const sceneCount = number(own(plan, 'sceneCount'), 'scene count', { nullable:false, min:1, max:8, integer:true });
    const covered = number(own(plan, 'covered'), 'covered scenes', { nullable:false, min:0, max:sceneCount, integer:true });
    const budget = object(own(input, 'budget') || {}, 'budget');
    const assumptions = object(own(budget, 'assumptions') || {}, 'budget assumptions');
    const result = object(own(budget, 'result') || {}, 'budget result');
    if (own(result, 'measured') === true || own(result, 'projection') === false) fail('this case cannot certify measured savings');
    const numericAssumptions = ['visitsBefore','visitsAfter','scouts','scoutRate','onsiteHours','travelHours','visitMiles','mileRate','toolCost','crew','days','crewRate','baselineMinutes','dailyRate','avoidableScoutUnits','hoursPerDay','routeMinutes'];
    const a = Object.fromEntries(numericAssumptions.map(k => [k, number(own(assumptions,k),k,{min:0,max:1e6})]));
    const billing = own(assumptions,'billing') || 'hourly';
    if (!['hourly','daily'].includes(billing)) fail('unknown scouting billing unit');
    Object.assign(a, { billing, paidTravel: own(assumptions,'paidTravel') === true,
      scoutCommitment:commitment(own(assumptions,'scoutCommitment')), crewCommitment:commitment(own(assumptions,'crewCommitment')), mileageCommitment:commitment(own(assumptions,'mileageCommitment')),
      rateSource:string(own(assumptions,'rateSource'),240,'rate source'), sourceNote:string(own(assumptions,'sourceNote'),600,'source note'), sourceStatus:string(own(assumptions,'sourceStatus'),60,'source status') });
    const numericResults = ['before','after','perVisit','scouting','crewTravel','total','visitsAvoided','modeledScenarioDelta','cashPotential','knownCashDelta','laborCapacityValue','scoutHoursReleased','scoutDaysReleased','crewHoursReleased','scoutLaborValue','mileageValue','crewLaborValue','avoidableScoutUnitsApplied'];
    const r = Object.fromEntries(numericResults.map(k => [k, number(own(result,k),k)]));
    const commitments = own(result,'commitments') || {};
    Object.assign(r, { cashUnresolved:list(own(result,'cashUnresolved'),12,'unresolved costs',v=>string(v,240,'unresolved cost',false)),
      commitments:{ scout:commitment(own(commitments,'scout')), crew:commitment(own(commitments,'crew')), mileage:commitment(own(commitments,'mileage')) }, projection:true, measured:false });
    const pilot = object(own(input,'pilot') || {},'pilot');
    const p = { baselineUnits:number(own(pilot,'baselineUnits'),'baseline units',{min:0,max:1e6}), actualUnits:number(own(pilot,'actualUnits'),'actual units',{min:0,max:1e6}),
      baselineCost:number(own(pilot,'baselineCost'),'baseline cost',{min:0,max:1e12}), actualCost:number(own(pilot,'actualCost'),'actual cost',{min:0,max:1e12}),
      source:string(own(pilot,'source'),600,'pilot source'), notes:string(own(pilot,'notes'),1200,'pilot notes'), status:'producer-reported; no causal savings verified' };
    const date = string(own(project,'date'),40,'review date');
    if (date && (!/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(date) || !Number.isFinite(Date.parse(date)))) fail('review date must be an ISO date');
    return freeze({ version:1,
      project:{ name:string(own(project,'name'),120,'project name'), reviewer:string(own(project,'reviewer'),120,'reviewer'), decision:string(own(project,'decision'),240,'decision'), date },
      plan:{ mode, current:requireCurrent ? true : false, fingerprint:identifier(own(plan,'fingerprint'),160,'plan fingerprint',false), sceneCount, covered,
        locations:number(own(plan,'locations'),'locations',{min:0,max:24,integer:true}), moves:number(own(plan,'moves'),'company moves',{min:0,max:23,integer:true}),
        propertyIds:list(own(plan,'propertyIds'),24,'property IDs',v=>identifier(v,64,'property ID',false)),
        unknowns:list(own(plan,'unknowns'),24,'unknowns',v=>string(v,300,'unknown',false)), constraintsSummary:string(own(plan,'constraintsSummary'),1200,'constraints summary'),
        sceneAssignments:list(own(plan,'sceneAssignments'),8,'scene assignments',row=> { object(row,'scene assignment'); return {
          sceneId:identifier(own(row,'sceneId') ?? own(row,'scene_id'),60,'scene ID',false), heading:string(own(row,'heading'),120,'scene heading'),
          propertyId:identifier(own(row,'propertyId') ?? own(row,'property_id'),64,'property ID'), shotId:identifier(own(row,'shotId') ?? own(row,'shot_id'),120,'shot ID'),
          decision:string(own(row,'decision'),240,'scene decision'), notes:string(own(row,'notes'),600,'scene notes') }; }) },
      budget:{assumptions:a,result:r},pilot:p,
      scope:'Projected decision case, not a filming approval, booking or verified customer savings report.' });
  }
  const normalizeCase = input => normalize(input,true);
  const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const usd = value => value == null ? 'Unknown' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(value);
  const shown = value => value == null ? 'Not reported' : String(value);
  function sections(input) {
    const c=normalizeCase(input), a=c.budget.assumptions, r=c.budget.result;
    return { c, blocks:[
      ['Producer review', [`Project: ${c.project.name || 'Untitled project'}`,`Reviewer: ${c.project.reviewer || 'Not reported'}`,`Decision (reported): ${c.project.decision || 'Pending producer review'}`,`Review date: ${c.project.date || 'Not reported'}`]],
      ['Current shortlist', [`${c.plan.mode.toUpperCase()} SOURCE MODE · ${c.plan.covered}/${c.plan.sceneCount} scenes covered · ${shown(c.plan.locations)} locations · ${shown(c.plan.moves)} company moves (one visit per property assumed)`, `Plan fingerprint: ${c.plan.fingerprint}`, `Constraints: ${c.plan.constraintsSummary || 'Not reported'}`, ...c.plan.sceneAssignments.map(s=>`${s.heading || s.sceneId}: property ${s.propertyId || 'unassigned'}, frame ${s.shotId || 'unassigned'}${s.decision ? ' · '+s.decision : ''}${s.notes ? ' · '+s.notes : ''}`)]],
      ['Projected budget, USD', [r.laborCapacityValue != null && r.laborCapacityValue < 0 ? `Scenario adds labor: ${usd(-r.laborCapacityValue)} of additional labor capacity would be required. This is not a saving.` : `Potential labor capacity value: ${usd(r.laborCapacityValue)}. Capacity value is not cash saved.`, `Potential avoidable cash, after entered tool cost: ${usd(r.cashPotential)}. ${r.cashPotential == null ? 'Cost avoidability is unresolved.' : 'Conditional on producer-reported cost commitments.'}`, `Known component cash delta: ${usd(r.knownCashDelta)}; unresolved components remain excluded, not assumed free.`, `Modeled scenario difference: ${usd(r.modeledScenarioDelta)}; this is not measured savings.`, `Tool/provider cost entered: ${usd(a.toolCost)}. Billing basis: ${a.billing}.`, `Scout commitment: ${a.scoutCommitment}; crew commitment: ${a.crewCommitment}; mileage commitment: ${a.mileageCommitment}.`, `Rate/source status: ${a.sourceStatus || 'Unspecified'} · ${a.rateSource || 'No source entered'}${a.sourceNote ? ' · '+a.sourceNote : ''}`, `Scouting units before / after: ${shown(a.visitsBefore)} / ${shown(a.visitsAfter)}. People: ${shown(a.scouts)}. ${a.billing === 'daily' ? 'Daily' : 'Hourly'} rate: ${usd(a.billing === 'daily' ? a.dailyRate : a.scoutRate)}.`, `On-site hours / round-trip travel hours per visit: ${shown(a.onsiteHours)} / ${shown(a.travelHours)}. Round-trip vehicle miles: ${shown(a.visitMiles)} at ${usd(a.mileRate)}/mile. Hourly labor inputs are not added in day-rate mode.`, `Explicit avoidable scout person-units cap: ${shown(a.avoidableScoutUnits)}. Hours per billable day: ${shown(a.hoursPerDay)}; absent daily hours are not inferred.`, `Paid crew travel included: ${a.paidTravel ? 'yes, projected' : 'no'}. Crew: ${shown(a.crew)}; shoot days: ${shown(a.days)}; paid hourly rate: ${usd(a.crewRate)}. Baseline / selected one-way minutes: ${shown(a.baselineMinutes)} / ${shown(a.routeMinutes)}. Uses one starting point, no live traffic, and cannot establish different employees’ home commutes.`, `Scout person-hours released: ${shown(r.scoutHoursReleased)}; scout person-days released: ${shown(r.scoutDaysReleased)}; crew paid-travel hours released: ${shown(r.crewHoursReleased)}.`, ...(r.cashUnresolved.length ? r.cashUnresolved.map(v=>`Unresolved: ${v}`) : [])]],
      ['Before a physical scout or filming commitment', [ 'Filming permission, owner access and operational availability are unknown until confirmed by the responsible person. A marketed lease listing is not filming permission.', 'Verify dimensions, access, sound, exits, utilities, parking and permit requirements on site. AI-imagined changes do not certify physical fit.', 'Event-licensed data does not establish continuing production rights. Confirm post-event data rights and inventory continuity before an ongoing company pilot.', ...c.plan.unknowns.map(v=>`Open check: ${v}`)]],
      ['Prospective pilot record — producer-reported', [`Baseline units / actual units: ${shown(c.pilot.baselineUnits)} / ${shown(c.pilot.actualUnits)}. Unit meaning and comparison method must be recorded in the source or notes.`, `Baseline cost / actual cost: ${usd(c.pilot.baselineCost)} / ${usd(c.pilot.actualCost)}.`, `Source: ${c.pilot.source || 'Not reported'}`, `Notes: ${c.pilot.notes || 'Not reported'}`, 'No causal savings or percentage reduction is calculated from this record. An estimate, shorter research session or smaller shortlist does not prove eliminated billable days.']]
    ] };
  }
  function renderText(input) {
    const {c,blocks}=sections(input);
    return ['TYPECAST · PRODUCER RECCE DECISION MEMO',c.scope,...blocks.flatMap(([title,lines])=>['',title,...lines.map(v=>'- '+v)])].join('\n');
  }
  function renderHtml(input) {
    const {c,blocks}=sections(input);
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Typecast producer decision memo</title><style>body{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:36px auto;padding:0 20px;color:#182120}h1{font-size:27px}h2{font-size:18px;margin-top:28px}li{margin:7px 0;overflow-wrap:anywhere}.scope{padding:12px;background:#fff6dc;border:1px solid #e6bc69}@media print{body{margin:0}section{break-inside:avoid}}</style><h1>Typecast · producer recce decision memo</h1><p class="scope">'+escape(c.scope)+'</p>'+blocks.map(([title,lines])=>'<section><h2>'+escape(title)+'</h2><ul>'+lines.map(v=>'<li>'+escape(v)+'</li>').join('')+'</ul></section>').join('')+'</html>';
  }
  function exportJson(input) { return JSON.stringify(normalizeCase(input),null,2); }
  function importCase(text) {
    if (typeof text !== 'string' || text.length > MAX_BYTES || new TextEncoder().encode(text).length > MAX_BYTES) fail('case file exceeds 100 KB');
    let parsed; try { parsed=JSON.parse(text); } catch { fail('invalid case JSON'); }
    return normalize(parsed,false);
  }
  const api={normalizeCase,renderHtml,renderText,exportJson,importCase};
  if(typeof module==='object'&&module.exports) module.exports=api; else root.TypecastProducerBrief=api;
})(typeof globalThis!=='undefined'?globalThis:this);
