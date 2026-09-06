(() => {
  'use strict';
  const root = document.querySelector('[data-walkthroughs]');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[data-tour-tab]')];
  const panels = [...root.querySelectorAll('[data-tour-panel]')];
  const videos = [...root.querySelectorAll('video')];
  const mobile = matchMedia('(max-width: 700px)');
  const setOrientation = () => root.querySelector('[role="tablist"]').setAttribute('aria-orientation', mobile.matches ? 'horizontal' : 'vertical');
  setOrientation(); mobile.addEventListener('change', setOrientation);
  const choose = (tab, focus = false) => {
    videos.forEach(video => video.pause());
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute('aria-selected', String(active)); item.tabIndex = active ? 0 : -1;
    });
    panels.forEach(panel => { panel.hidden = panel.dataset.tourPanel !== tab.dataset.tourTab; });
    if (focus) tab.focus();
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => choose(tab));
    tab.addEventListener('keydown', event => {
      const keys = mobile.matches ? ['ArrowLeft', 'ArrowRight'] : ['ArrowUp', 'ArrowDown'];
      let next;
      if (event.key === keys[0]) next = (index + tabs.length - 1) % tabs.length;
      if (event.key === keys[1]) next = (index + 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault(); choose(tabs[next], true);
    });
  });
  videos.forEach(video => {
    video.addEventListener('play', () => videos.filter(other => other !== video).forEach(other => other.pause()));
    const panel = video.closest('[data-tour-panel]');
    const play = panel.querySelector('[data-tour-play]');
    video.hidden = true; play.hidden = false;
    play.addEventListener('click', async () => {
      play.hidden = true; video.hidden = false;
      try { await video.play(); video.focus(); }
      catch { panel.querySelector('[data-tour-status]').textContent = 'Playback could not start. Try the video’s Play control, or read the walkthrough below.'; }
    });
  });
})();
