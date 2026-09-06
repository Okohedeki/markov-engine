(() => {
  'use strict';
  const root = document.querySelector('[data-idea-story]');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[data-story-tab]')];
  const panels = [...root.querySelectorAll('[data-story-panel]')];
  const select = (name, focus = false) => {
    tabs.forEach(tab => {
      const active = tab.dataset.storyTab === name;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });
    panels.forEach(panel => { panel.hidden = panel.dataset.storyPanel !== name; });
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab.dataset.storyTab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      select(tabs[next].dataset.storyTab, true);
    });
  });
  root.querySelectorAll('[data-story-next]').forEach(button => {
    button.addEventListener('click', () => select(button.dataset.storyNext, true));
  });
  root.querySelectorAll('[data-demo-idea]').forEach(button => {
    button.addEventListener('click', () => {
      const angle = window.MarkovExamples?.[0]?.angles[Number(button.dataset.demoIdea)];
      if (!angle) return;
      root.querySelector('[data-story-hook]').textContent = angle[1];
      root.querySelector('[data-story-summary]').textContent = angle[2];
      const outline = root.querySelector('[data-story-outline]');
      outline.replaceChildren(...angle[3].split('\n').map(text => {
        const item = document.createElement('li');
        item.textContent = text;
        return item;
      }));
      select('draft', true);
    });
  });
})();
