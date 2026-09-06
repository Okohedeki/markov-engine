(() => {
  'use strict';
  const root = document.querySelector('[data-source-trail]');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[data-trail-tab]')];
  const panels = [...root.querySelectorAll('[data-trail-panel]')];
  const treatments = [...root.querySelectorAll('[data-trail-treatment]')];
  const picks = [...root.querySelectorAll('[data-trail-pick]')];
  const status = root.querySelector('[data-trail-status]');
  const fallback = root.querySelector('[data-trail-fallback]');
  const film = root.querySelector('[data-source-film]');
  if (film) {
    const video = film.querySelector('video');
    film.addEventListener('toggle', () => { if (!film.open) video.pause(); });
    video.addEventListener('error', () => {
      film.querySelector('[data-source-film-status]').textContent = 'Playback is unavailable. Download the recording or explore the same steps below.';
    });
  }
  let selected = 'beer';

  function chooseIdea(id) {
    if (!treatments.some(item => item.dataset.trailTreatment === id)) return;
    selected = id;
    treatments.forEach(item => { item.hidden = item.dataset.trailTreatment !== id; });
    picks.forEach(item => item.setAttribute('aria-pressed', String(item.dataset.trailPick === id)));
    status.textContent = '';
    fallback.hidden = true;
  }

  function chooseStep(name, focus = false) {
    if (!tabs.some(tab => tab.dataset.trailTab === name)) return;
    tabs.forEach(tab => {
      const active = tab.dataset.trailTab === name;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });
    panels.forEach(panel => { panel.hidden = panel.dataset.trailPanel !== name; });
  }

  root.dataset.enhanced = '';
  const navigation = root.querySelector('[data-trail-tabs]');
  navigation.hidden = false;
  navigation.setAttribute('role', 'tablist');
  tabs.forEach((tab, index) => {
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', `trail-${tab.dataset.trailTab}`);
    tab.addEventListener('click', () => chooseStep(tab.dataset.trailTab));
    tab.addEventListener('keydown', event => {
      const positions = {ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1};
      if (!(event.key in positions)) return;
      event.preventDefault();
      chooseStep(tabs[positions[event.key]].dataset.trailTab, true);
    });
  });
  panels.forEach(panel => {
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', `trail-tab-${panel.dataset.trailPanel}`);
    panel.tabIndex = 0;
  });
  root.querySelectorAll('[data-trail-next]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => chooseStep(button.dataset.trailNext, true));
  });
  root.querySelectorAll('[data-trail-idea]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => {
      chooseIdea(button.dataset.trailIdea);
      chooseStep('script', true);
    });
  });
  picks.forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => chooseIdea(button.dataset.trailPick));
  });
  const related = [...root.querySelectorAll('[data-trail-related]')];
  related.forEach(item => item.addEventListener('toggle', () => {
    if (item.open) related.forEach(other => { if (other !== item) other.open = false; });
  }));
  root.querySelector('[data-trail-tools]').hidden = false;

  function outline() {
    const article = treatments.find(item => item.dataset.trailTreatment === selected);
    const beats = [...article.querySelectorAll('.trail-outline li')].map((item, index) => `${index + 1}. ${item.textContent.trim()}`);
    const sources = [...article.querySelectorAll('.trail-attached-sources a')].map(link => `- ${link.textContent.replace('↗', '').trim()}: ${link.href}`);
    return `# ${article.querySelector('h3').textContent.trim()}\n\nEditorial example, not a live Markov run. Sources checked 5 September 2026.\n\n## Hook\n${article.querySelector('[data-trail-hook]').textContent.trim()}\n\n## What makes it different\n${article.querySelector('.trail-difference p').textContent.trim()}\n\n## Outline\n${beats.join('\n\n')}\n\n## Reporting boundary\n${article.querySelector('.trail-boundary').textContent.trim()}\n\n## Sources\n${sources.join('\n')}\n`;
  }

  root.querySelector('[data-trail-copy]').addEventListener('click', async () => {
    const text = outline();
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = 'Copied the idea, outline, reporting boundaries and source links.';
    } catch {
      fallback.hidden = false;
      const textarea = fallback.querySelector('textarea');
      textarea.value = text;
      textarea.focus();
      textarea.select();
      status.textContent = 'Automatic copying is unavailable. Your outline is selected below; copy it manually.';
    }
  });
  root.querySelector('[data-trail-download]').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([outline()], {type: 'text/markdown;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = `markov-script-idea-${selected}.md`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status.textContent = 'Outline downloaded with its sources and reporting boundaries.';
  });
  function followHash() {
    if (location.hash === '#walkthroughs' && film) film.open = true;
    if (location.hash === '#source-notes') root.querySelector('#source-notes').open = true;
    const name = location.hash.replace('#trail-', '');
    if (['source', 'connections', 'script'].includes(name)) {
      chooseStep(name);
      root.scrollIntoView({block: 'start', behavior: 'instant'});
    }
  }
  root.querySelectorAll('a[href="#source-notes"]').forEach(link => link.addEventListener('click', () => { root.querySelector('#source-notes').open = true; }));
  chooseIdea('beer');
  chooseStep('connections');
  followHash();
  // Native fragment scrolling can run after deferred scripts on first load.
  window.addEventListener('load', () => requestAnimationFrame(followHash), {once: true});
  window.addEventListener('hashchange', followHash);
})();
