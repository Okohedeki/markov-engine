(() => {
  const modes = document.querySelectorAll('[data-mode-picker] input[name="mode"]');
  const scriptFields = document.querySelectorAll('[data-script-fields]');
  if (modes.length && scriptFields.length) {
    const syncMode = () => {
      const selected = document.querySelector('[data-mode-picker] input[name="mode"]:checked');
      scriptFields.forEach((field) => {
        field.hidden = !selected || selected.value !== 'script';
      });
    };

    modes.forEach((input) => input.addEventListener('change', syncMode));
    syncMode();
  }

  document.querySelectorAll('[data-sample-switcher]').forEach((switcher) => {
    const tabs = [...switcher.querySelectorAll('[data-sample-tab]')];
    const panels = [...switcher.querySelectorAll('[data-sample-panel]')];
    const select = (name) => {
      tabs.forEach((tab) => {
        const active = tab.dataset.sampleTab === name;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.samplePanel !== name;
      });
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => select(tab.dataset.sampleTab));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault();
        const offset = event.key === 'ArrowRight' ? 1 : -1;
        const next = tabs[(index + offset + tabs.length) % tabs.length];
        select(next.dataset.sampleTab);
        next.focus();
      });
    });
  });
})();
