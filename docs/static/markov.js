(() => {
  const modes = document.querySelectorAll('[data-mode-picker] input[name="mode"]');
  const scriptFields = document.querySelectorAll('[data-script-fields]');
  if (!modes.length || !scriptFields.length) return;

  const syncMode = () => {
    const selected = document.querySelector('[data-mode-picker] input[name="mode"]:checked');
    scriptFields.forEach((field) => {
      field.hidden = !selected || selected.value !== 'script';
    });
  };

  modes.forEach((input) => input.addEventListener('change', syncMode));
  syncMode();
})();
