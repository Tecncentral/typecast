'use strict';
// Director's Room chrome: the inspector tabs. Pure presentation; staging state lives in director.js.
(() => {
  const tabs = [...document.querySelectorAll('.tabs [role="tab"]')];
  if (!tabs.length) return;
  const KEY = 'typecast.director.tab';
  function select(tab, focus = false) {
    for (const t of tabs) {
      const on = t === tab;
      t.setAttribute('aria-selected', String(on));
      t.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(t.getAttribute('aria-controls'));
      if (panel) panel.hidden = !on;
    }
    if (focus) tab.focus();
    try { sessionStorage.setItem(KEY, tab.id); } catch { /* storage may be blocked */ }
  }
  // Mode switching hides some tabs with CSS; keyboard navigation only visits the visible ones.
  const visible = () => tabs.filter((t) => getComputedStyle(t).display !== 'none');
  tabs.forEach((tab) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', (e) => {
      const vis = visible(), i = vis.indexOf(tab), step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      if (step) { e.preventDefault(); select(vis[(i + step + vis.length) % vis.length], true); }
      else if (e.key === 'Home') { e.preventDefault(); select(vis[0], true); }
      else if (e.key === 'End') { e.preventDefault(); select(vis[vis.length - 1], true); }
    });
  });
  window.TypecastTabs = { select: (id) => { const t = document.getElementById(id); if (t) select(t); } };
  let saved = null;
  try { saved = sessionStorage.getItem(KEY); } catch { /* storage may be blocked */ }
  const start = tabs.find((t) => t.id === saved);
  if (start) select(start);

  // A proposal or a reel in progress pulls its tab forward so the review step is never hidden.
  const reveal = (panelId, tabId) => {
    const node = document.getElementById(panelId);
    if (!node) return;
    new MutationObserver(() => {
      if (!node.hidden) select(document.getElementById(tabId));
    }).observe(node, { attributes: true, attributeFilter: ['hidden'] });
  };
  reveal('proposal', 'tab-alt');
  reveal('cancelReel', 'tab-export');
  reveal('projectReview', 'tab-export');

  // Space plays or pauses when focus is not in a text control.
  document.addEventListener('keydown', (e) => {
    if (e.key !== ' ' || e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t.closest('input, textarea, select, button, [role="tab"], summary, a, dialog')) return;
    const play = document.getElementById('play'), pause = document.getElementById('pause');
    // director.js is a classic script, so its top-level state is visible here.
    const playing = typeof S !== 'undefined' && !!S.play?.on;
    e.preventDefault();
    (playing ? pause : play)?.click();
  });
})();
