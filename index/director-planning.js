'use strict';
(function () {
  const $ = id => document.getElementById(id);
  let origin = null, map = null, pin = null, layer = null, L = null;
  let imageBusy = false, imageFrame = null;
  let latestCase = null, importedAgainst, requireRebuild = false, lastStored = '';
  let formRevision = 0, importSeq = 0, currentFingerprint = null, decisionBound = null;
  const CASE_KEY = 'typecast-producer-budget-v1';
  const imageContext = s => JSON.stringify([s?.selectedScene, s?.selectedShot, $('instr')?.value.trim()]);
  const money = n => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(n);
  const fields = [
    ['visitsBefore', 'In-person scout visits before Typecast', 10, 1], ['visitsAfter', 'Visits still needed after Typecast', 3, 1],
    ['scouts', 'People per scouting visit', 2, 1], ['scoutRate', 'Scouting labor / person / hour ($)', 40, 1],
    ['onsiteHours', 'On-site hours per scouting visit', 2, 0.5], ['travelHours', 'Round-trip travel hours per visit', 1, 0.5],
    ['visitMiles', 'Round-trip vehicle miles per visit', 30, 1], ['mileRate', 'Vehicle cost / mile ($)', 0.7, 0.01],
    ['toolCost', 'Typecast + provider cost for this project ($)', 0, 1], ['crew', 'Paid traveling crew members', 20, 1],
    ['days', 'Shoot days at this location', 3, 1], ['crewRate', 'Paid travel labor / person / hour ($)', 30, 1],
    ['baselineMinutes', 'Previous location: one-way drive (minutes)', 60, 1],
  ];
  const caseFields = ['scoutBilling','dailyScoutRate','scoutCommitment','crewCommitment','mileageCommitment','avoidableScoutUnits','costSourceStatus','costSourceNote','producerName','producerReviewer','producerDecision','pilotBaselineUnits','pilotActualUnits','pilotBaselineCost','pilotActualCost','pilotSource','pilotNotes'];
  const formIds = () => [...fields.map(([k])=>'cost_'+k),...caseFields];
  function formState() { return {version:1,fields:Object.fromEntries(formIds().map(id=>[id,$(id).value])),paidTravel:$('paidTravel').checked}; }
  // True only when the browser copy matches the open form (or the producer has not opted in). A refused write
  // withdraws the opt-in instead of claiming a persistence that did not happen.
  function saveForm() {
    if (!$('keepProducerCase')?.checked) return true;
    try { const text = JSON.stringify(formState()); if (text !== lastStored) { localStorage.setItem(CASE_KEY,text); lastStored=text; } return true; }
    catch { $('keepProducerCase').checked=false; $('producerCaseStatus').textContent='Browser storage unavailable; this budget case was not saved. Download a budget case instead.'; return false; }
  }
  // Verified removal: a refused delete must not be reported as a clear.
  function purgeStored() {
    lastStored='';
    try { localStorage.removeItem(CASE_KEY); return localStorage.getItem(CASE_KEY)===null; } catch { return false; }
  }
  function applyForm(value) {
    if (!value || value.version!==1 || !value.fields || typeof value.fields!=='object') throw new Error('Unsupported saved budget form.');
    for (const id of formIds()) {
      const v = value.fields[id];
      if (typeof v === 'string' && v.length<=1200) $(id).value=v;
    }
    $('paidTravel').checked=value.paidTravel===true;
  }
  function download(content, type, extension) {
    const url=URL.createObjectURL(new Blob([content],{type})), link=document.createElement('a');
    link.href=url; link.download=`typecast-producer-case.${extension}`; document.body.append(link); link.click(); link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function commute() {
    return $('commuteOn')?.checked && origin ? { ...origin, max_minutes: Number($('driveLimit').value) } : null;
  }
  function changed() {
    $('driveLabel').textContent = `${$('driveLimit').value} min one way`;
    $('commuteNote').textContent = $('commuteOn').checked ? (origin ?
      'Drive limit changed? Build plan to apply it. Unknown or unreachable routes are excluded. No live traffic.' :
      'Choose the employee’s home or a production base on the map first.') : 'Drive filter is off.';
    if (map && origin && L) {
      if (layer) layer.remove();
      // An illustrative geographic circle, never the actual road-time filter.
      layer = L.circle([origin.lat, origin.lon], { radius: Number($('driveLimit').value) / 60 * 35 * 1609.344 / 1.3,
        color: '#edbd69', weight: 1, fillOpacity: 0.07 }).addTo(map);
    }
    render();
  }
  function setOrigin(lat, lon) {
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return;
    origin = { lat, lon };
    $('originLat').value = lat.toFixed(6); $('originLon').value = lon.toFixed(6);
    $('originText').textContent = `Starting pin: ${lat.toFixed(4)}, ${lon.toFixed(4)}`;
    if (map && L) {
      if (!pin) { pin = L.marker([lat, lon], { draggable: true }).addTo(map); pin.on('dragend', () => { const p = pin.getLatLng(); setOrigin(p.lat, p.lng); }); }
      else pin.setLatLng([lat, lon]);
    }
    changed();
  }
  function render() {
    if (!$('costResult') || !$('cost_visitsBefore')) return;
    const s = window.typecastPlanningSnapshot?.();
    if (!s) return;
    saveForm();
    if (imageFrame && imageFrame !== imageContext(s)) {
      $('customImagePreview').replaceChildren(); $('customImagePreview').hidden = true; imageFrame = null;
      $('customImageStatus').textContent = 'Frame changed. Generate a new image for this frame.';
    }
    const a = Object.fromEntries(fields.map(([k]) => [k, $('cost_' + k).value.trim() === '' ? NaN : Number($('cost_' + k).value)]));
    a.paidTravel = $('paidTravel').checked;
    a.billing = $('scoutBilling').value;
    // Blank means unknown (null), never NaN: NaN made a legitimate hourly-mode case unexportable.
    a.dailyRate = $('dailyScoutRate').value.trim() === '' ? null : Number($('dailyScoutRate').value);
    for (const k of ['scoutCommitment','crewCommitment','mileageCommitment']) a[k] = $(k).value;
    a.avoidableScoutUnits = $('avoidableScoutUnits').value.trim() === '' ? null : Number($('avoidableScoutUnits').value);
    a.rateSource = $('costSourceNote').value.trim(); a.sourceNote = 'Reviewer-entered source; applicability not independently verified.';
    a.sourceStatus = $('costSourceStatus').value;
    $('cost_visitsBefore').parentElement.firstChild.textContent = a.billing === 'daily' ? 'Billable scout days before Typecast' : 'In-person scout visits before Typecast';
    $('cost_visitsAfter').parentElement.firstChild.textContent = a.billing === 'daily' ? 'Billable scout days still needed' : 'Visits still needed after Typecast';
    const rows = s.assignments.map(x => s.response?.scenes?.find(sc => sc.id === x.scene_id)?.candidates?.find(c => c.shot.shot_id === x.shot_id));
    if (requireRebuild && s.response && s.response !== importedAgainst) requireRebuild = false;
    const complete = s.mode !== 'community' && !!s.plan && !s.stale && !requireRebuild && !(s.plan.uncovered_scene_ids || []).length && rows.length === s.sceneCount && rows.every(c => c && c.eligible !== false);
    const routes = rows.map(c => c?.commute?.status === 'estimated' ? c.commute.minutes : null);
    const route = routes.length && routes.every(v => typeof v === 'number' && Number.isFinite(v)) ? Math.max(...routes) : null;
    a.routeMinutes = route;
    const result = TypecastCosts.estimate(a, route, complete);
    const c = commute();
    const matches = c && s.response ? s.response.scenes.flatMap(sc => sc.candidates || []).filter(x => x.commute?.status === 'estimated' && x.commute.minutes <= c.max_minutes) : [];
    $('drivePreview').textContent = c && s.response ? `${new Set(matches.map(x => x.shot.property_id)).size} cached candidate properties within ${c.max_minutes} min. Build plan to apply the current limit.` : '';
    // Visible summary tiles (drive limit, scouting scenario, location vs set) live in director-impact.js.
    window.TypecastImpact?.render?.({ snapshot: s, result, assumptions: a, commute: c, route, complete });
    const box = $('costResult'); box.replaceChildren();
    latestCase = null; currentFingerprint = null;
    for (const id of ['exportProducerHtml','exportProducerJson']) $(id).disabled = !!result.error;
    const line = (tag, text) => { const el = document.createElement(tag); el.textContent = text; box.append(el); };
    if (result.error) { line('p', result.error); return; }
    line('h3', result.cashPotential == null ? 'Cash impact: unconfirmed' : `${money(Math.abs(result.cashPotential))} ${result.cashPotential >= 0 ? 'potential cash avoided' : 'additional cash cost'} / project`);
    const added = result.visitsAvoided < 0, scoutUnit = result.scoutDaysReleased != null ? 'person-days' : 'person-hours', scoutQty = result.scoutDaysReleased ?? result.scoutHoursReleased;
    line('p', `SCENARIO · ${result.laborCapacityValue < 0 ? `Additional labor required: ${money(-result.laborCapacityValue)}` : `Labor capacity value: ${money(result.laborCapacityValue)}`}. This is not payroll saved. ${scoutQty == null ? 'Scout hours unknown: no hours per day entered.' : scoutQty < 0 ? `${-scoutQty} additional scout ${scoutUnit} required.` : `${scoutQty} scout ${scoutUnit} potentially released.`}`);
    for (const unresolved of result.cashUnresolved) line('p', unresolved);
    line('p', `Scouting: ${money(result.before)} before → ${money(result.after)} after; ${added ? `${-result.visitsAvoided} more` : `${result.visitsAvoided} fewer`} ${a.billing === 'daily' ? 'billable scout days' : 'visits'} assumed${added ? ' (added cost)' : ''}.`);
    line('p', a.billing === 'daily' ? `Per day: ${a.scouts} scout(s) × ${money(a.dailyRate)}/day + ${a.visitMiles} mi × ${money(a.mileRate)}/mi = ${money(result.perVisit)}. Hourly inputs ignored in day-rate mode.` : `Per visit: ${a.scouts} × ${money(a.scoutRate)}/h × (${a.onsiteHours} on-site + ${a.travelHours} travel hours) + ${a.visitMiles} mi × ${money(a.mileRate)}/mi = ${money(result.perVisit)}.`);
    if (result.crewTravel !== null) line('p', `Paid crew travel: ${money(result.crewTravel)} change. (${a.baselineMinutes} − ${route.toFixed(1)}) min × 2 trips × ${a.crew} crew × ${a.days} days × ${money(a.crewRate)}/h ÷ 60. Uses the slowest selected location from this one starting pin.`);
    else line('p', 'Crew travel excluded: enable paid travel and build a plan with known routes to include it.');
    line('p', `${s.response?.mode === 'mock' ? 'MOCK PLAN · ' : ''}Illustrative editable assumptions. No measured studio savings, live market prices, set-construction savings or guaranteed visit reduction. Physical inspection and permission still required.`);
    try {
      const assignments = s.assignments.map(x=>{
        const seen=new Set([x.property_id]);
        const alternatives=(s.response.scenes.find(sc=>sc.id===x.scene_id)?.candidates||[]).filter(c=>{const id=c.shot?.property_id;if(!id||seen.has(id))return false;seen.add(id);return true;}).slice(0,2);
        const notes=alternatives.map(c=>`Alternative ${c.shot.property_id}: ${c.eligible===false?'excluded by planner':'retained for review'}; ${(c.warnings||[]).map(w=>w.message).filter(Boolean).slice(0,2).join('; ')||'no additional warning supplied'}`).join(' | ').slice(0,600);
        return {sceneId:x.scene_id,propertyId:x.property_id,shotId:x.shot_id,heading:s.scenes?.find(sc=>sc.id===x.scene_id)?.heading || x.scene_id,
          decision:'Selected within the retrieved pool by scene coverage, location count and visual similarity; not a lowest-cost or filming-permission certification.',notes};
      });
      let hash = 2166136261;
      const signature = JSON.stringify([s.response.mode,assignments,s.response.commute_limit_minutes,routes,s.plan.property_ids]);
      for (const ch of signature) hash = Math.imul(hash ^ ch.charCodeAt(0),16777619);
      const fingerprint = `plan:${(hash>>>0).toString(16)}`;
      const unknowns = [...new Set(rows.flatMap(c=>(c.warnings||[]).map(w=>String(w.message||'').slice(0,300))).filter(Boolean))].slice(0,20);
      if (s.rejected?.length) unknowns.push(`Producer rejected properties: ${s.rejected.join(', ').slice(0,240)}. Record reasons in the decision.`);
      // Free-text reasoning belongs to the plan it was written against; never let it silently describe a different shortlist.
      if ($('producerDecision').value.trim() && decisionBound !== fingerprint)
        unknowns.push(decisionBound ? `Reviewer decision text was written for an earlier plan (${decisionBound}); re-read it before relying on it for ${fingerprint}.`
          : 'Reviewer decision text was restored from a file or browser copy, or typed before this plan existed; confirm it applies to this plan.');
      unknowns.push('A marketed lease listing does not establish filming permission or current owner access.');
      currentFingerprint = fingerprint;
      const optional = id => $(id).value.trim()==='' ? null : Number($(id).value);
      latestCase = TypecastProducerBrief.normalizeCase({version:1,project:{name:$('producerName').value,reviewer:$('producerReviewer').value,decision:$('producerDecision').value,date:new Date().toISOString()},
        plan:{current:true,mode:s.response.mode,fingerprint,sceneCount:s.sceneCount,covered:assignments.length,locations:s.plan.locations,moves:s.plan.company_moves,
          propertyIds:[...new Set(assignments.map(x=>x.propertyId))],unknowns,sceneAssignments:assignments,
          constraintsSummary:`Selected retrieved plan; maximum ${s.limits?.maxLocations ?? '?'} locations, ${s.limits?.trucks ?? '?'} trucks and ${s.limits?.cars ?? '?'} crew cars; require available listing: ${s.limits?.requireAvailable ? 'yes' : 'no'}. One visit per property assumed. One-way commute limit: ${s.response.commute_limit_minutes ?? 'off'} minutes; no live traffic. Starting coordinates omitted. Filming permission not established.`},
        budget:{assumptions:a,result},pilot:{baselineUnits:optional('pilotBaselineUnits'),actualUnits:optional('pilotActualUnits'),baselineCost:optional('pilotBaselineCost'),actualCost:optional('pilotActualCost'),source:$('pilotSource').value,notes:$('pilotNotes').value}});
    } catch (e) {
      for (const id of ['exportProducerHtml','exportProducerJson']) $(id).disabled = true;
      $('producerCaseStatus').textContent = e.message;
    }
  }
  window.TypecastPlanning = { constraints: () => { const c = commute(); return c ? { commute: c } : {}; }, render,
    validate: () => $('commuteOn')?.checked && !origin ? 'Place a starting pin before enabling the commute filter.' : null };
  window.addEventListener('DOMContentLoaded', async () => {
    if (!$('driveLimit')) return;
    for (const [key, title, value, step] of fields) {
      const label = document.createElement('label'); label.textContent = title;
      const input = document.createElement('input'); Object.assign(input, { id: 'cost_' + key, type: 'number', min: '0', max: '1000000', step: String(step), value: String(value) });
      input.addEventListener('input', () => { formRevision++; render(); }); label.append(input); $('costInputs').append(label);
    }
    $('paidTravel').addEventListener('change', () => { formRevision++; render(); });
    for (const id of caseFields) $(id).addEventListener('input', () => { formRevision++; render(); });
    // Registered after the render above, so the fingerprint is current when the reviewer's text is bound to it.
    $('producerDecision').addEventListener('input', () => { decisionBound = currentFingerprint; });
    $('keepProducerCase').addEventListener('change', () => {
      if ($('keepProducerCase').checked) { if (saveForm()) $('producerCaseStatus').textContent='This current budget case is stored in this browser. Use JSON files for separate projects.'; }
      else $('producerCaseStatus').textContent = purgeStored() ? 'Browser copy removed. Open values are unchanged.' : 'Could not remove the browser copy (storage refused). No further saves will be made; clear this site’s data in browser settings.';
    });
    $('clearProducerCase').addEventListener('click', () => {
      const removed = purgeStored();
      $('keepProducerCase').checked=false;
      $('producerCaseStatus').textContent = removed ? 'Stored budget case cleared. Open values remain; they will not be saved again unless you opt in.'
        : 'Could not clear the stored budget case (storage refused). It may still exist; no further saves will be made. Clear this site’s data in browser settings.';
    });
    for (const [id,kind] of [['exportProducerHtml','html'],['exportProducerJson','json']]) $(id).addEventListener('click', () => {
      render();
      if (!latestCase) return void ($('producerCaseStatus').textContent='Build a current complete plan and enter valid assumptions before exporting.');
      try {
        download(kind==='html'?TypecastProducerBrief.renderHtml(latestCase):TypecastProducerBrief.exportJson(latestCase),kind==='html'?'text/html':'application/json',kind);
        $('producerCaseStatus').textContent='Exported current decision with assumptions, source mode and open checks. No filming approval or verified savings created.';
      } catch (e) { $('producerCaseStatus').textContent=e.message; }
    });
    $('importProducerJson').addEventListener('change', async e => {
      const file=e.target.files?.[0]; e.target.value=''; if (!file) return;
      // The most recently chosen file wins, and any edit made while a file is being read wins over the file.
      const revision=formRevision, seq=++importSeq;
      try {
        if (file.size>100000) throw new Error('Budget case exceeds 100 KB.');
        const c=TypecastProducerBrief.importCase(await file.text()), a=c.budget.assumptions;
        if (seq!==importSeq) return;   // superseded by a newer file; stay silent so the newer result's status is kept
        if (formRevision!==revision) throw new Error('Inputs changed while the file was loading; current inputs were retained.');
        // A field the file does not contain becomes blank (unknown), never the previous project's value or an invented default.
        for (const [k] of fields) $('cost_'+k).value=a[k]==null?'':String(a[k]);
        for (const [id,k] of [['scoutBilling','billing'],['dailyScoutRate','dailyRate'],['scoutCommitment','scoutCommitment'],['crewCommitment','crewCommitment'],['mileageCommitment','mileageCommitment'],['avoidableScoutUnits','avoidableScoutUnits'],['costSourceStatus','sourceStatus'],['costSourceNote','rateSource']]) $(id).value=a[k]==null?'':String(a[k]);
        $('paidTravel').checked=a.paidTravel;
        for (const [id,k] of [['producerName','name'],['producerReviewer','reviewer'],['producerDecision','decision']]) $(id).value=c.project[k]||'';
        for (const [id,k] of [['pilotBaselineUnits','baselineUnits'],['pilotActualUnits','actualUnits'],['pilotBaselineCost','baselineCost'],['pilotActualCost','actualCost'],['pilotSource','source'],['pilotNotes','notes']]) $(id).value=c.pilot[k]==null?'':String(c.pilot[k]);
        decisionBound=null; formRevision++;
        importedAgainst=window.typecastPlanningSnapshot?.().response; requireRebuild=true; render();
        $('producerCaseStatus').textContent='Restored assumptions and producer-reported pilot fields only. Build plan to bind them to current evidence; saved results and approvals were not restored.';
      } catch(e) { $('producerCaseStatus').textContent=`Could not restore budget case: ${e.message}`; }
    });
    $('instr').addEventListener('input', render);
    $('scoutBilling').addEventListener('change', () => { formRevision++; render(); }); $('dailyScoutRate').addEventListener('input', render);
    $('commercialRatePreset').addEventListener('click', () => {
      $('scoutBilling').value = 'daily'; $('dailyScoutRate').value = '957.58';
      for (const [k,v] of Object.entries({visitsBefore:5,visitsAfter:2,scouts:1,visitMiles:0,toolCost:0})) $('cost_'+k).value = String(v);
      for (const k of ['scoutCommitment','crewCommitment','mileageCommitment']) $(k).value='unconfirmed';
      $('avoidableScoutUnits').value=''; $('costSourceStatus').value='rate_reference';
      $('costSourceNote').value='Local 399 / AICP covered commercial minimum, effective June 28, 2026: https://www.ht399.org/app/uploads/2026/06/APPENDIX-A-Wage-Chart-Drivers-and-Locations-final-6.24.26.pdf';
      formRevision++;
      $('paidTravel').checked = false; render();
    });
    $('customizeImage').addEventListener('click', async () => {
      if (imageBusy) return;
      const s = window.typecastPlanningSnapshot?.(), instruction = $('instr').value.trim();
      const note = $('customImageStatus'), preview = $('customImagePreview');
      if (!s?.selectedShot || s.response?.mode !== 'live') return void (note.textContent = 'Build a live plan and select a real indexed frame first.');
      if (!instruction) return void (note.textContent = 'Describe the props, characters, lighting or scene change in Direction above.');
      if (!$('imageConsent').checked) return void (note.textContent = 'Confirm sending this frame to your configured image provider first.');
      imageBusy = true; $('customizeImage').disabled = true; imageFrame = imageContext(s);
      const sentContext = imageFrame;
      preview.hidden = true; preview.replaceChildren(); note.textContent = 'Generating one imagined frame. Your real room and takes are unchanged. This may take several minutes.';
      try {
        const response = await fetch('/api/production/customize-image', { method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({shot_id:s.selectedShot,instruction,confirm_image_upload:true}) });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Image request failed (${response.status})`);
        if (imageContext(window.typecastPlanningSnapshot?.()) !== sentContext) { note.textContent = 'Image finished for an earlier scene, frame or direction; it was not applied to this scene.'; return; }
        if (!/^\/api\/production\/customization\/[a-f0-9]{32}\.png$/.test(data.image_url)) throw new Error('Invalid image response');
        for (const [label, url] of [['REAL INDEXED FRAME',`/image/${encodeURIComponent(s.selectedShot)}`],['AI-IMAGINED SCENE · NOT THE REAL ROOM',data.image_url]]) {
          const figure = document.createElement('figure'), caption = document.createElement('figcaption'), image = document.createElement('img');
          caption.textContent = label; image.alt = label; image.src = url; image.style.width = '100%';
          figure.append(caption,image); preview.append(figure);
        }
        const link = document.createElement('a'); link.href = data.image_url; link.textContent = 'Download labeled AI preview'; link.download = 'typecast-imagined-scene.png'; preview.append(link);
        preview.hidden = false; note.textContent = 'Concept image only. Architecture may differ; verify all dimensions and feasibility. Your source evidence and A/B takes were retained.';
      } catch (e) { note.textContent = `${e.message}. Original retained; no substitute generated.`; }
      finally { imageBusy = false; $('customizeImage').disabled = false; }
    });
    $('driveLimit').addEventListener('input', changed); $('commuteOn').addEventListener('change', changed);
    $('setCoordinates').addEventListener('click', () => {
      const lat = $('originLat').value.trim(), lon = $('originLon').value.trim();
      if (!lat || !lon || !Number.isFinite(Number(lat)) || !Number.isFinite(Number(lon)) || Math.abs(Number(lat)) > 90 || Math.abs(Number(lon)) > 180)
        return void ($('commuteNote').textContent = 'Enter valid latitude (−90 to 90) and longitude (−180 to 180).');
      setOrigin(Number(lat), Number(lon)); map?.setView([Number(lat), Number(lon)], 12);
    });
    for (const [id, lat, lon] of [['originLA',34.0522,-118.2437],['originHouston',29.7604,-95.3698]]) $(id).addEventListener('click', () => { setOrigin(lat,lon); map?.setView([lat,lon],11); });
    $('useMyLocation').addEventListener('click', () => {
      if (!navigator.geolocation) return void ($('commuteNote').textContent = 'Geolocation unavailable. Place a map pin instead.');
      navigator.geolocation.getCurrentPosition(p => { setOrigin(p.coords.latitude,p.coords.longitude); map?.setView([p.coords.latitude,p.coords.longitude],13); }, () => { $('commuteNote').textContent = 'Location unavailable. Place a map pin instead.'; }, { timeout: 10000 });
    });
    try {
      const saved=localStorage.getItem(CASE_KEY);
      if (saved && saved.length>30000) $('producerCaseStatus').textContent='A saved browser budget is too large to restore and was ignored. Use Clear stored budget case to remove it.';
      else if (saved) { applyForm(JSON.parse(saved)); $('keepProducerCase').checked=true; lastStored=saved; $('producerCaseStatus').textContent='Budget inputs restored from this browser. Build a current plan before exporting a decision.'; }
    } catch { $('producerCaseStatus').textContent='Saved browser budget unavailable; nothing was overwritten. Use a JSON case if available.'; }
    changed();
    try {
      L = await import('/app/vendor/leaflet/leaflet-src.esm.js');
      map = L.map('commuteMap', { scrollWheelZoom: false }).setView([34.0522,-118.2437],10);
      $('commuteSection').addEventListener('toggle', () => map.invalidateSize());
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);
      map.on('click', e => setOrigin(e.latlng.lat,e.latlng.lng));
      if (origin) setOrigin(origin.lat,origin.lon);
    } catch { $('commuteNote').textContent = 'Map unavailable. Use the coordinate fields or current-location button.'; }
  });
})();
