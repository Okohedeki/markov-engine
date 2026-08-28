(() => {
  const modes = document.querySelectorAll('[data-mode-picker] input[name="mode"]');
  const scriptFields = document.querySelectorAll('[data-script-fields]');
  if (modes.length && scriptFields.length) {
    const advancedOptions = document.querySelector('[data-advanced-options]');
    const syncMode = () => {
      const selected = document.querySelector('[data-mode-picker] input[name="mode"]:checked');
      scriptFields.forEach((field) => {
        field.hidden = !selected || selected.value !== 'script';
      });
      if (advancedOptions && selected && selected.value === 'script') {
        advancedOptions.open = true;
      }
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
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let nextIndex = index;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = tabs.length - 1;
        if (['ArrowRight', 'ArrowDown'].includes(event.key)) nextIndex = (index + 1) % tabs.length;
        if (['ArrowLeft', 'ArrowUp'].includes(event.key)) nextIndex = (index - 1 + tabs.length) % tabs.length;
        const next = tabs[nextIndex];
        select(next.dataset.sampleTab);
        next.focus();
      });
    });
  });
})();
