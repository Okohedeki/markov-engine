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
    });
  });

  all("[data-route-toggle]").forEach((button) => {
    on(button, "click", () => {
      const card = button.closest("[data-route-card]");
      const panel = card?.querySelector("[data-route-panel]");
      const open = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(open));
      if (panel) panel.hidden = !open;
      card?.classList.toggle("is-open", open);
    });
  });

  all("[data-reject-opportunity]").forEach((button) => {
    on(button, "click", () => {
      const card = button.closest("[data-route-card]") || button.parentElement;
      const form = card?.querySelector("[data-rejection-reason]");
      if (!form) return;
      form.hidden = false;
      form.querySelector("input")?.focus();
    });
  });

  const composer = document.querySelector("[data-output-composer]");
  let composerTrigger = null;
  const closeComposer = () => {
    if (!composer?.open) return;
    composer.close();
    composerTrigger?.focus();
  };
  all("[data-open-composer]").forEach((button) => {
    on(button, "click", () => {
      if (!composer) return;
      composerTrigger = button;
      const topic = composer.querySelector("[data-composer-topic]");
      const angle = composer.querySelector("[data-composer-angle]");
      const context = composer.querySelector("[data-composer-context]");
      if (topic) topic.value = button.dataset.topicId || "";
      if (angle) angle.value = button.dataset.topicFocus || "";
      if (context) context.textContent = `Working from “${button.dataset.topicTitle || "this route"}”.`;
      composer.showModal();
      requestAnimationFrame(() => angle?.focus());
    });
  });
  all("[data-close-composer]").forEach((button) => on(button, "click", closeComposer));
  on(composer, "click", (event) => {
    const bounds = composer.getBoundingClientRect();
    const outside = event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom;
    if (outside) closeComposer();
  });
  on(composer, "cancel", (event) => {
    event.preventDefault();
    closeComposer();
  });

  on(document, "keydown", (event) => {
    if (event.key === "Escape") {
      setPublicNav(false);
      setAppNav(false);
    }
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target?.isContentEditable;
    if (event.key === "/" && !typing) {
      const search = document.querySelector('a[href="/app/search"]');
      if (search) {
        event.preventDefault();
        search.click();
      }
    }
  });
})();
