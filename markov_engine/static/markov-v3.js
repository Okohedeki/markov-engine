(() => {
  const navToggle = document.querySelector('[data-nav-toggle]');
  const siteNav = document.querySelector('[data-site-nav]');
  if (navToggle && siteNav) {
    const setOpen = (open) => {
      navToggle.setAttribute('aria-expanded', String(open));
      siteNav.dataset.open = String(open);
    };
    navToggle.addEventListener('click', () => setOpen(navToggle.getAttribute('aria-expanded') !== 'true'));
    siteNav.addEventListener('click', (event) => {
      if (event.target.closest('a')) setOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') setOpen(false);
    });
  }

  const campaign = document.querySelector('[data-campaign-demo]');
  if (campaign) {
    const treatments = {
      flagship: {
        label: 'CANONICAL ARTICLE / WEEK 1', note: 'Own the full argument',
        title: 'Follow the missing buyer, not the dramatic seller.',
        rows: [
          ['Job', 'Establish the mechanism, compare the competing selloff story, and name the data that would change the conclusion.'],
          ['Distinct contribution', 'A referenceable model of marginal Treasury demand with every source role attached.'],
          ['Monitor next', 'Allocation guidance, sector-level flows, and audience questions about replacement buyers.'],
        ],
      },
      newsletter: {
        label: 'NEWSLETTER / WEEK 1', note: 'Invite the informed reader in',
        title: 'The Treasury signal hiding before the sale.',
        rows: [
          ['Job', 'Make the buyer-side question legible in a shorter editorial note.'],
          ['Distinct contribution', 'A compact chart of hedged yields and three questions for readers who track global capital.'],
          ['Monitor next', 'Replies that reveal which institution or data series needs a deeper follow-up.'],
        ],
      },
      video: {
        label: 'VIDEO ESSAY / WEEK 2', note: 'Make the mechanism visible',
        title: 'Japan’s Treasury story is not really about a dump.',
        rows: [
          ['Job', 'Walk viewers through the institutions between demographics and an asset flow.'],
          ['Distinct contribution', 'A visual mechanism showing yields, mandates, hedging, and marginal demand.'],
          ['Monitor next', 'Retention at the mechanism turn and questions about who replaces Japanese demand.'],
        ],
      },
      social: {
        label: 'LINKEDIN + SHORTS / WEEK 2', note: 'Open the argument, do not flatten it',
        title: 'A selloff is not the only way a buyer can move a market.',
        rows: [
          ['Job', 'Introduce one surprising distinction and point to the canonical explanation.'],
          ['Distinct contribution', 'A focused prompt asking which demand signal matters before instrument-level sales.'],
          ['Monitor next', 'Qualified disagreement, missing examples, and language the audience uses for the problem.'],
        ],
      },
    };
    const tabs = [...campaign.querySelectorAll('[data-campaign-tab]')];
    const label = campaign.querySelector('[data-campaign-label]');
    const title = campaign.querySelector('[data-campaign-title]');
    const body = campaign.querySelector('[data-campaign-body]');
    const note = campaign.querySelector('.v3-treatment header small');
    const select = (name, moveFocus = false) => {
      const treatment = treatments[name];
      if (!treatment) return;
      tabs.forEach((tab) => {
        const active = tab.dataset.campaignTab === name;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && moveFocus) tab.focus();
      });
      label.textContent = treatment.label;
      note.textContent = treatment.note;
      title.textContent = treatment.title;
      body.replaceChildren(...treatment.rows.map(([heading, copy]) => {
        const section = document.createElement('section');
        const span = document.createElement('span');
        const paragraph = document.createElement('p');
        span.textContent = heading;
        paragraph.textContent = copy;
        section.append(span, paragraph);
        return section;
      }));
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => select(tab.dataset.campaignTab));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        select(tabs[next].dataset.campaignTab, true);
      });
    });
  }

  document.querySelectorAll('[data-signal-type]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-signal-type]').forEach((item) => {
        item.setAttribute('aria-pressed', String(item === button));
      });
      const input = document.querySelector('[data-signal-input]');
      if (input) {
        input.placeholder = button.dataset.placeholder || 'Add a signal…';
        input.focus();
      }
    });
  });

  document.querySelectorAll('[data-reject-opportunity]').forEach((button) => {
    button.addEventListener('click', () => {
      const reason = button.closest('[data-opportunity]')?.querySelector('[data-rejection-reason]');
      if (reason) reason.hidden = !reason.hidden;
    });
  });
})();
