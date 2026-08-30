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

  const v6Hero = document.querySelector('[data-v6-hero]');
  if (v6Hero) {
    const demo = v6Hero.querySelector('[data-v6-demo]');
    const opportunity = v6Hero.querySelector('.v6-opportunity');
    const sourceButtons = [...v6Hero.querySelectorAll('[data-v6-source]')];
    const noticed = v6Hero.querySelector('[data-v6-noticed]');
    const opportunityTitle = v6Hero.querySelector('[data-v6-opportunity]');
    const detail = v6Hero.querySelector('[data-v6-detail]');
    const strength = v6Hero.querySelector('[data-v6-strength]');
    const states = {
      article: {
        noticed: 'Coverage moves from demographic pressure directly to a Treasury selloff.',
        opportunity: 'Follow the missing buyer—not the dramatic seller.',
        detail: 'The first useful signal may be weaker new demand, before any visible sale.',
        strength: 'High information gain',
      },
      answer: {
        noticed: 'Portfolio research shows that institutions adjust through mandates, liabilities, and currency costs—not one national decision.',
        opportunity: 'Name the institutional turn between yields and demand.',
        detail: 'Test which mandates and hedging conditions could change the marginal allocation.',
        strength: 'Primary-source mechanism',
      },
      audience: {
        noticed: 'The open question identifies the part current coverage leaves unresolved: who absorbs gradually weaker demand.',
        opportunity: 'Turn the selloff question into a replacement-buyer map.',
        detail: 'Follow the financing consequence while preserving uncertainty about the size and timing of the shift.',
        strength: 'Open research thread',
      },
    };
    const selectSource = (name, moveFocus = false) => {
      const state = states[name];
      if (!state) return;
      sourceButtons.forEach((button) => {
        const active = button.dataset.v6Source === name;
        button.setAttribute('aria-selected', String(active));
        button.tabIndex = active ? 0 : -1;
        if (active && moveFocus) button.focus();
      });
      noticed.textContent = state.noticed;
      opportunityTitle.textContent = state.opportunity;
      detail.textContent = state.detail;
      strength.textContent = state.strength;
      opportunity.classList.remove('is-changing');
      void opportunity.offsetWidth;
      opportunity.classList.add('is-changing');
    };
    sourceButtons.forEach((button, index) => {
      button.addEventListener('click', () => selectSource(button.dataset.v6Source));
      button.addEventListener('keydown', (event) => {
        if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (['ArrowUp', 'ArrowLeft'].includes(event.key)) next = (index - 1 + sourceButtons.length) % sourceButtons.length;
        if (['ArrowDown', 'ArrowRight'].includes(event.key)) next = (index + 1) % sourceButtons.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = sourceButtons.length - 1;
        selectSource(sourceButtons[next].dataset.v6Source, true);
      });
    });

    const canTilt = window.matchMedia('(pointer: fine)').matches && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (demo && canTilt) {
      let frame;
      demo.addEventListener('pointermove', (event) => {
        if (frame) cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          const bounds = demo.getBoundingClientRect();
          const x = (event.clientX - bounds.left) / bounds.width - .5;
          const y = (event.clientY - bounds.top) / bounds.height - .5;
          demo.style.setProperty('--v6-tilt-x', `${(-y * 2.4).toFixed(2)}deg`);
          demo.style.setProperty('--v6-tilt-y', `${(x * 3.2).toFixed(2)}deg`);
        });
      });
      demo.addEventListener('pointerleave', () => {
        demo.style.setProperty('--v6-tilt-x', '0deg');
        demo.style.setProperty('--v6-tilt-y', '0deg');
      });
    }
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
