(() => {
  const studio = document.querySelector('[data-v7-outputs]');
  if (!studio) return;

  const states = {
    brief: {
      label: 'DECISION BRIEF',
      title: 'The first Treasury signal may be the buyer who never arrives.',
      body: 'A visible selloff is not required for Japanese allocation changes to matter. Higher domestic yields, institutional mandates, and hedging costs can weaken marginal buying before old holdings move.',
      evidence: 'Domestic allocation proposals establish timing; the demand effect remains an interpretation pending aligned flow data.',
    },
    report: {
      label: 'RESEARCH REPORT',
      title: 'From domestic yields to marginal Treasury demand.',
      body: 'The report follows the institutional path in detail: policy timing, pension mandates, currency hedging, portfolio incentives, existing holdings, new purchases, and the competing explanations for observed flows.',
      evidence: 'Each mechanism step keeps its source role, qualification, and unresolved data need beside the argument it affects.',
    },
    script: {
      label: 'FACTUAL SCRIPT',
      title: 'Japan does not need to dump Treasuries to change the story.',
      body: 'The opening rejects the dramatic selloff frame, then walks viewers through the slower buyer-side mechanism and names the data that would confirm or break it.',
      evidence: 'Source cues, caveats, and visual evidence prompts remain attached to the relevant section of the script.',
    },
    newsletter: {
      label: 'NEWSLETTER',
      title: 'The Treasury signal hiding before the sale.',
      body: 'A concise editorial note gives readers the buyer-side distinction, the four-step mechanism, and three developments worth watching next.',
      evidence: 'The note links the policy signal, primary research, and open flow question without presenting interpretation as settled fact.',
    },
  };

  const tabs = [...studio.querySelectorAll('[data-v7-output]')];
  const label = studio.querySelector('[data-v7-output-label]');
  const title = studio.querySelector('[data-v7-output-title]');
  const body = studio.querySelector('[data-v7-output-body]');
  const evidence = studio.querySelector('[data-v7-output-evidence]');

  const select = (name, moveFocus = false) => {
    const state = states[name];
    if (!state) return;
    tabs.forEach((tab) => {
      const active = tab.dataset.v7Output === name;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && moveFocus) tab.focus();
    });
    label.textContent = state.label;
    title.textContent = state.title;
    body.textContent = state.body;
    evidence.textContent = state.evidence;
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab.dataset.v7Output));
    tab.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let next = index;
      if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      select(tabs[next].dataset.v7Output, true);
    });
  });
})();
