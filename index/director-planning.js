'use strict';
(function () {
  const $ = id => document.getElementById(id);
  let origin = null, map = null, pin = null, layer = null, L = null;
  let imageBusy = false, imageFrame = null;
  const imageContext = s => JSON.stringify([s?.selectedScene, s?.selectedShot, $('instr')?.value.trim()]);
  const money = n => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
  const fields = [
    ['visitsBefore', 'In-person scout visits before Typecast', 10, 1], ['visitsAfter', 'Visits still needed after Typecast', 3, 1],
    ['scouts', 'People per scouting visit', 2, 1], ['scoutRate', 'Scouting labor / person / hour ($)', 40, 1],
    ['onsiteHours', 'On-site hours per scouting visit', 2, 0.5], ['travelHours', 'Round-trip travel hours per visit', 1, 0.5],
    ['visitMiles', 'Round-trip vehicle miles per visit', 30, 1], ['mileRate', 'Vehicle cost / mile ($)', 0.7, 0.01],
    ['toolCost', 'Typecast + provider cost for this project ($)', 0, 1], ['crew', 'Paid traveling crew members', 20, 1],
    ['days', 'Shoot days at this location', 3, 1], ['crewRate', 'Paid travel labor / person / hour ($)', 30, 1],
    ['baselineMinutes', 'Previous location: one-way drive (minutes)', 60, 1],
  ];
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
    if (imageFrame && imageFrame !== imageContext(s)) {
      $('customImagePreview').replaceChildren(); $('customImagePreview').hidden = true; imageFrame = null;
      $('customImageStatus').textContent = 'Frame changed. Generate a new image for this frame.';
    }
    const a = Object.fromEntries(fields.map(([k]) => [k, $('cost_' + k).value.trim() === '' ? NaN : Number($('cost_' + k).value)]));
    a.paidTravel = $('paidTravel').checked;
    a.billing = $('scoutBilling').value;
    a.dailyRate = $('dailyScoutRate').value.trim() === '' ? NaN : Number($('dailyScoutRate').value);
    $('cost_visitsBefore').parentElement.firstChild.textContent = a.billing === 'daily' ? 'Billable scout days before Typecast' : 'In-person scout visits before Typecast';
    $('cost_visitsAfter').parentElement.firstChild.textContent = a.billing === 'daily' ? 'Billable scout days still needed' : 'Visits still needed after Typecast';
    const rows = s.assignments.map(x => s.response?.scenes?.find(sc => sc.id === x.scene_id)?.candidates?.find(c => c.shot.shot_id === x.shot_id));
    const complete = !!s.plan && !s.stale && !(s.plan.uncovered_scene_ids || []).length && rows.length === s.sceneCount && rows.every(c => c && c.eligible !== false);
    const routes = rows.map(c => c?.commute?.status === 'estimated' ? c.commute.minutes : null);
    const route = routes.length && routes.every(v => typeof v === 'number' && Number.isFinite(v)) ? Math.max(...routes) : null;
    const result = TypecastCosts.estimate(a, route, complete);
    const c = commute();
    const matches = c && s.response ? s.response.scenes.flatMap(sc => sc.candidates || []).filter(x => x.commute?.status === 'estimated' && x.commute.minutes <= c.max_minutes) : [];
    $('drivePreview').textContent = c && s.response ? `${new Set(matches.map(x => x.shot.property_id)).size} cached candidate properties within ${c.max_minutes} min. Build plan to apply the current limit.` : '';
    const box = $('costResult'); box.replaceChildren();
    const line = (tag, text) => { const el = document.createElement(tag); el.textContent = text; box.append(el); };
    if (result.error) { line('p', result.error); return; }
    line('h3', `${money(result.total)} ${result.total >= 0 ? 'potential savings' : 'additional cost'} / project`);
    line('p', `Scouting: ${money(result.before)} before → ${money(result.after)} after; ${result.visitsAvoided} fewer ${a.billing === 'daily' ? 'billable scout days' : 'visits'} assumed.`);
    line('p', a.billing === 'daily' ? `Per day: ${a.scouts} scout(s) × ${money(a.dailyRate)}/day + ${a.visitMiles} mi × ${money(a.mileRate)}/mi = ${money(result.perVisit)}. Hourly inputs ignored in day-rate mode.` : `Per visit: ${a.scouts} × ${money(a.scoutRate)}/h × (${a.onsiteHours} on-site + ${a.travelHours} travel hours) + ${a.visitMiles} mi × ${money(a.mileRate)}/mi = ${money(result.perVisit)}.`);
    if (result.crewTravel !== null) line('p', `Paid crew travel: ${money(result.crewTravel)} change. (${a.baselineMinutes} − ${route.toFixed(1)}) min × 2 trips × ${a.crew} crew × ${a.days} days × ${money(a.crewRate)}/h ÷ 60. Uses the slowest selected location from this one starting pin.`);
    else line('p', 'Crew travel excluded: enable paid travel and build a plan with known routes to include it.');
    line('p', `${s.response?.mode === 'mock' ? 'MOCK PLAN · ' : ''}Illustrative editable assumptions. No measured studio savings, live market prices, set-construction savings or guaranteed visit reduction. Physical inspection and permission still required.`);
  }
  window.TypecastPlanning = { constraints: () => { const c = commute(); return c ? { commute: c } : {}; }, render,
    validate: () => $('commuteOn')?.checked && !origin ? 'Place a starting pin before enabling the commute filter.' : null };
  window.addEventListener('DOMContentLoaded', async () => {
    if (!$('driveLimit')) return;
    for (const [key, title, value, step] of fields) {
      const label = document.createElement('label'); label.textContent = title;
      const input = document.createElement('input'); Object.assign(input, { id: 'cost_' + key, type: 'number', min: '0', max: '1000000', step: String(step), value: String(value) });
      input.addEventListener('input', render); label.append(input); $('costInputs').append(label);
    }
    $('paidTravel').addEventListener('change', render);
    $('instr').addEventListener('input', render);
    $('scoutBilling').addEventListener('change', render); $('dailyScoutRate').addEventListener('input', render);
    $('commercialRatePreset').addEventListener('click', () => {
      $('scoutBilling').value = 'daily'; $('dailyScoutRate').value = '957.58';
      for (const [k,v] of Object.entries({visitsBefore:5,visitsAfter:2,scouts:1,visitMiles:0,toolCost:0})) $('cost_'+k).value = String(v);
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
