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

  const opportunityExplorer = document.querySelector('[data-opportunity-explorer]');
  if (opportunityExplorer) {
    const tabs = [...opportunityExplorer.querySelectorAll('[data-explorer-tab]')];
    const panels = [...opportunityExplorer.querySelectorAll('[data-explorer-panel]')];
    const status = opportunityExplorer.querySelector('[data-explorer-status]');
    const labels = {
      search: 'Search results',
      ai: 'AI answers',
      coverage: 'Competitor coverage',
      history: 'Previous work',
    };
    const select = (name, moveFocus = false) => {
      tabs.forEach((tab) => {
        const active = tab.dataset.explorerTab === name;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && moveFocus) tab.focus();
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.explorerPanel !== name;
      });
      if (status) status.textContent = `Viewing ${labels[name] || name}`;
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => select(tab.dataset.explorerTab));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        select(tabs[next].dataset.explorerTab, true);
      });
    });
  }

  const opportunityStory = document.querySelector('[data-opportunity-story]');
  if (opportunityStory) {
    const tabs = [...opportunityStory.querySelectorAll('[data-story-tab]')];
    const panels = [...opportunityStory.querySelectorAll('[data-story-panel]')];
    const markers = [...opportunityStory.querySelectorAll('[data-story-marker]')];
    const counter = opportunityStory.querySelector('[data-story-counter]');
    const select = (name, moveFocus = false) => {
      const selectedIndex = tabs.findIndex((tab) => tab.dataset.storyTab === name);
      if (selectedIndex < 0) return;
      tabs.forEach((tab, index) => {
        const active = index === selectedIndex;
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && moveFocus) tab.focus();
      });
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.storyPanel !== name;
      });
      if (counter) counter.textContent = `${String(selectedIndex + 1).padStart(2, '0')} / ${String(tabs.length).padStart(2, '0')}`;
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => select(tab.dataset.storyTab));
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (['ArrowUp', 'ArrowLeft'].includes(event.key)) next = (index - 1 + tabs.length) % tabs.length;
        if (['ArrowDown', 'ArrowRight'].includes(event.key)) next = (index + 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        select(tabs[next].dataset.storyTab, true);
      });
    });

    const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const desktopStoryQuery = window.matchMedia('(min-width: 761px)');
    let storyObserver;
    const syncStoryObserver = () => {
      storyObserver?.disconnect();
      storyObserver = undefined;
      if (!('IntersectionObserver' in window) || reducedMotionQuery.matches || !desktopStoryQuery.matches) return;
      storyObserver = new IntersectionObserver((entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) select(visible.target.dataset.storyMarker);
      }, { rootMargin: '-32% 0px -48% 0px', threshold: [0, 0.2, 0.6] });
      markers.forEach((marker) => storyObserver.observe(marker));
    };
    syncStoryObserver();
    reducedMotionQuery.addEventListener('change', syncStoryObserver);
    desktopStoryQuery.addEventListener('change', syncStoryObserver);

    const directionButtons = [...opportunityStory.querySelectorAll('[data-direction]')];
    const directionTitle = opportunityStory.querySelector('[data-direction-title]');
    const directionAudience = opportunityStory.querySelector('[data-direction-audience]');
    const directionWhy = opportunityStory.querySelector('[data-direction-why]');
    const directionWeakness = opportunityStory.querySelector('[data-direction-weakness]');
    directionButtons.forEach((button) => {
      button.addEventListener('click', () => {
        directionButtons.forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
        if (directionTitle) directionTitle.textContent = button.dataset.title;
        if (directionAudience) directionAudience.textContent = button.dataset.audience;
        if (directionWhy) directionWhy.textContent = button.dataset.why;
        if (directionWeakness) directionWeakness.textContent = button.dataset.weakness;
      });
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
