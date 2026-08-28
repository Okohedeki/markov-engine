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

  const ideaDemo = document.querySelector('[data-idea-demo]');
  if (ideaDemo) {
    const route = (phrase, steps, options = {}) => ({ phrase, steps, ...options });
    const examples = {
      article: {
        sourceLabel: 'Article thesis',
        startCopy: 'You started with a sentence.',
        sentenceText: 'Japan’s aging population could force it to sell U.S. Treasuries.',
        sentence: [
          'Japan’s ',
          { route: 'aging', text: 'aging population' },
          ' could ',
          { route: 'force', text: 'force' },
          ' it to ',
          { route: 'treasuries', text: 'sell U.S. Treasuries' },
          '.',
        ],
        routes: {
          aging: route('aging population', [
            ['Context', 'What does this phrase actually imply?', 'Demographic aging'],
            ['Mechanism', 'How could demographics affect investment?', 'Pension obligations'],
            ['Hidden intermediary', 'Which institutions translate saving into assets?', 'Insurers and pension funds'],
            ['Constraint', 'Where could their portfolios turn?', 'Domestic capital demand and Japanese yields', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'Demography changes the decision-makers and their constraints; it does not mechanically determine one asset sale.',
            evidence: ['Inspect Japan’s Statistical Handbook, page 28', 'https://www.stat.go.jp/english/data/handbook/pdf/2025all.pdf'],
            angle: 'The market signal may appear first in the institutions adapting to longevity—not in Treasury holdings themselves.',
            mechanism: 'Insurers and pension funds translate longer lives into duration, liability, and allocation decisions.',
            comparison: 'Aging may increase aggregate saving while still changing which institutions hold foreign assets.',
          }),
          force: route('force', [
            ['Missing premise', 'What would create the pressure?', 'Higher Japanese yields'],
            ['Mechanism', 'What changes the relative return?', 'Currency-hedging costs'],
            ['Hidden intermediary', 'Who makes the allocation decision?', 'Insurer portfolio committees'],
            ['Consequence', 'What could happen next?', 'Reduced demand for foreign bonds', 'Stronger interpretation', 'evidence'],
          ], {
            note: 'The original sentence skips four steps between demographics and Treasury selling.',
            evidence: ['Inspect the BOJ Financial System Report, page 28', 'https://www.boj.or.jp/en/research/brp/fsr/data/fsr231020a.pdf'],
            angle: 'The real risk may be gradual portfolio repricing driven by Japanese rates and currency-hedging economics.',
            mechanism: 'The pressure runs through relative yields, hedge costs, and insurer portfolio rules—not through demography alone.',
            comparison: 'A sudden forced selloff needs more evidence; gradual repricing has the stronger mechanism.',
          }),
          treasuries: route('sell U.S. Treasuries', [
            ['Ownership', 'Who actually owns the assets?', 'Government, banks, insurers, and funds'],
            ['Evidence', 'What happened during earlier rate shifts?', 'Hedge ratios moved before headline holdings'],
            ['Consequence', 'How might demand transmit to the U.S.?', 'Marginal auction demand and yields'],
            ['Test', 'Which explanation survives?', 'Track repricing before declaring a dump', 'Needs more evidence', 'warning'],
          ], {
            branches: [
              ['Sudden forced selloff', 'Needs more evidence', ''],
              ['Gradual portfolio repricing', 'Stronger path', 'strong'],
            ],
            note: 'Headline ownership is not the same as the marginal decision that moves price.',
            evidence: ['Inspect the U.S. Treasury foreign-portfolio survey', 'https://home.treasury.gov/news/press-releases/sb0482'],
            angle: 'Watch hedging demand and portfolio repricing before treating aggregate holdings as the leading signal.',
            mechanism: 'Different Japanese holders face different liabilities, mandates, and hedging choices.',
            comparison: 'The forced-sale story is dramatic; the gradual-demand story is more defensible and observable.',
          }),
        },
      },
      youtube: {
        sourceLabel: 'YouTube argument',
        startCopy: 'You started with a video.',
        sentenceText: 'Nuclear power is too slow to matter for near-term climate targets.',
        sentence: [
          'Nuclear power is ', { route: 'slow', text: 'too slow' }, ' to ',
          { route: 'matter', text: 'matter' }, ' for ',
          { route: 'targets', text: 'near-term climate targets' }, '.',
        ],
        routes: {
          slow: route('too slow', [
            ['Definition', 'Slow compared with what?', 'New-build completion dates'],
            ['Constraint', 'What governs the schedule?', 'Permitting, supply chains, and financing'],
            ['Alternative', 'Is every nuclear option a new build?', 'Life extensions and restarts'],
            ['Conclusion', 'What survives the comparison?', 'Speed depends on the intervention', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'A fleet extension and a first-of-a-kind reactor do not share one timeline.',
            angle: 'The useful comparison is not nuclear versus urgency; it is which nuclear intervention can change the grid before the deadline.',
            mechanism: 'Project type determines the critical path and therefore the emissions window it can affect.',
            comparison: 'New construction may miss a target while extensions or restarts can affect the same period.',
          }),
          matter: route('matter', [
            ['Outcome', 'What result counts as mattering?', 'Avoided fossil generation'],
            ['Intermediary', 'What converts capacity into impact?', 'Grid dispatch and reliability needs'],
            ['Weakener', 'What can erase the benefit?', 'Delay, cost, or displaced alternatives'],
            ['Test', 'What should be measured?', 'System emissions over the target window', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'Installed capacity is not the outcome; displaced generation over time is.',
            angle: 'A technology matters when it changes system dispatch inside the target window, not merely when it appears in a capacity forecast.',
            mechanism: 'Grid dispatch translates a project into avoided generation and reliability value.',
            comparison: 'Capacity, energy, and avoided emissions answer different questions.',
          }),
          targets: route('near-term climate targets', [
            ['Deadline', 'Which target and which year?', 'A bounded emissions budget'],
            ['Dependency', 'What retires before then?', 'Coal and gas generation'],
            ['Constraint', 'What can replace firm output?', 'Generation, storage, and transmission'],
            ['Conclusion', 'Where is the real bottleneck?', 'Replacement sequence, not one technology', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'A deadline turns the argument into a sequencing problem.',
            angle: 'The hidden question is whether the replacement portfolio arrives in the same order as fossil retirements.',
            mechanism: 'Retirements, interconnection, and firm-capacity replacement jointly determine the target path.',
            comparison: 'A technology ranking can obscure the system sequence that actually governs emissions.',
          }),
        },
      },
      tiktok: {
        sourceLabel: 'TikTok claim',
        startCopy: 'You started with 10 seconds.',
        sentenceText: 'Remote work is quietly hollowing out city tax bases.',
        sentence: [
          { route: 'remote', text: 'Remote work' }, ' is quietly ',
          { route: 'hollowing', text: 'hollowing out' }, ' ',
          { route: 'tax', text: 'city tax bases' }, '.',
        ],
        routes: {
          remote: route('Remote work', [
            ['Behavior', 'What changed first?', 'Commute frequency'],
            ['Mechanism', 'What follows fewer trips?', 'Lower office occupancy'],
            ['Spillover', 'Who loses nearby demand?', 'Transit and downtown businesses'],
            ['Test', 'Is the change permanent?', 'Track weekday activity over time', 'Needs more evidence', 'warning'],
          ], {
            note: 'A work-location change reaches public finance through several local markets.',
            angle: 'The leading signal may be weekday activity, not population loss.',
            mechanism: 'Commutes connect work location to office demand, transit use, and local spending.',
            comparison: 'Residential activity may offset some downtown losses, so the geography matters.',
          }),
          hollowing: route('hollowing out', [
            ['Meaning', 'Which revenue is actually shrinking?', 'Commercial assessments and local sales'],
            ['Delay', 'Why might budgets look stable at first?', 'Assessment and lease lags'],
            ['Intermediary', 'What converts vacancies into revenue?', 'Property valuations'],
            ['Consequence', 'What breaks next?', 'Service cuts or higher rates', 'Plausible hypothesis', 'warning'],
          ], {
            note: '“Hollowing out” hides timing differences between occupancy, valuation, and collection.',
            angle: 'The fiscal shock may arrive years after the behavioral change because assessment systems move slowly.',
            mechanism: 'Lease resets and property assessments delay the transmission from vacancies to budgets.',
            comparison: 'Immediate retail losses and delayed property-tax losses should not be treated as one event.',
          }),
          tax: route('city tax bases', [
            ['Composition', 'Which taxes fund this city?', 'Property, sales, income, and fees'],
            ['Exposure', 'Which base depends on downtown?', 'The local revenue mix'],
            ['Response', 'Can policy offset the loss?', 'Rates, land use, and service redesign'],
            ['Conclusion', 'Is every city equally exposed?', 'No—the tax structure controls the risk', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'The same remote-work shift can produce different fiscal outcomes under different tax systems.',
            angle: 'Remote work is not one municipal crisis; it is a stress test of each city’s revenue design.',
            mechanism: 'Tax composition converts the same behavior into different public-finance exposure.',
            comparison: 'Cities dependent on commercial property or commuter taxes face a different path from diversified cities.',
          }),
        },
      },
      pdf: {
        sourceLabel: 'PDF finding',
        startCopy: 'You started with a paper.',
        sentenceText: 'Heat pumps can reduce household emissions even on today’s grid.',
        sentence: [
          { route: 'pumps', text: 'Heat pumps' }, ' can ',
          { route: 'reduce', text: 'reduce household emissions' }, ' even on ',
          { route: 'grid', text: 'today’s grid' }, '.',
        ],
        routes: {
          pumps: route('Heat pumps', [
            ['Mechanism', 'How is heat produced?', 'Move heat rather than create it'],
            ['Measure', 'What captures the advantage?', 'Coefficient of performance'],
            ['Constraint', 'What changes in cold weather?', 'Efficiency and backup heat'],
            ['Test', 'What should the PDF report?', 'Seasonal performance, not a nameplate value', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'The relevant performance is seasonal and local, not a single laboratory number.',
            angle: 'The argument turns on when and where the heat pump draws power, not simply whether it is electric.',
            mechanism: 'Seasonal efficiency determines the electricity needed to displace a unit of fuel heat.',
            comparison: 'Average efficiency can hide the winter hours that dominate grid and emissions effects.',
          }),
          reduce: route('reduce household emissions', [
            ['Baseline', 'Which fuel is displaced?', 'Gas, oil, or resistance heat'],
            ['Accounting', 'Which electricity emissions count?', 'Marginal generation'],
            ['Timing', 'When does the load appear?', 'Cold, high-demand hours'],
            ['Conclusion', 'What decides the sign?', 'Displaced fuel versus marginal power', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'The comparison requires both sides of the substitution.',
            angle: 'A heat pump’s emissions value is a time-matched substitution calculation, not a generic grid average.',
            mechanism: 'The displaced combustion and the marginal electricity source jointly determine avoided emissions.',
            comparison: 'Annual averages can disagree with the winter marginal system that serves the new load.',
          }),
          grid: route('today’s grid', [
            ['Definition', 'Which grid and which hour?', 'Local marginal supply'],
            ['Constraint', 'Can the network serve winter peaks?', 'Distribution capacity'],
            ['Change', 'Will the grid stay the same?', 'Generation retires and connects'],
            ['Next step', 'What evidence resolves it?', 'Hourly regional modeling', 'Needs more evidence', 'warning'],
          ], {
            note: '“Today’s grid” is not one emissions factor or one physical constraint.',
            angle: 'The grid question is local and hourly: a national annual average can conceal the binding condition.',
            mechanism: 'Regional dispatch and distribution capacity connect new electric heat to system emissions.',
            comparison: 'A clean annual mix can still have a carbon-intensive or constrained winter margin.',
          }),
        },
      },
      audio: {
        sourceLabel: 'Podcast quote',
        startCopy: 'You started with a podcast.',
        sentenceText: 'Weight-loss drugs may reshape more than healthcare spending.',
        sentence: [
          { route: 'drugs', text: 'Weight-loss drugs' }, ' may ',
          { route: 'reshape', text: 'reshape more than' }, ' ',
          { route: 'spending', text: 'healthcare spending' }, '.',
        ],
        routes: {
          drugs: route('Weight-loss drugs', [
            ['Mechanism', 'What behavior changes first?', 'Appetite and food choice'],
            ['Constraint', 'Who continues treatment?', 'Access, price, and adherence'],
            ['Intermediary', 'Who feels the demand change?', 'Grocers, restaurants, and brands'],
            ['Test', 'What is signal versus novelty?', 'Persistent category-level purchasing', 'Needs more evidence', 'warning'],
          ], {
            note: 'Prescription growth does not directly measure durable consumer behavior.',
            angle: 'The earliest non-health signal may be a shift in the composition of food demand, not total spending.',
            mechanism: 'Adherence converts a clinical intervention into repeated household purchasing decisions.',
            comparison: 'Short-term novelty effects must be separated from durable category substitution.',
          }),
          reshape: route('reshape more than', [
            ['Scope', 'Which adjacent systems could move?', 'Food, apparel, travel, and labor'],
            ['Filter', 'Which link is most direct?', 'Repeated consumption behavior'],
            ['Weakener', 'What could limit spillovers?', 'Discontinuation and unequal access'],
            ['Conclusion', 'What is defensible now?', 'A portfolio of testable demand shifts', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'A broad forecast becomes useful only after it is decomposed into observable channels.',
            angle: 'Treat the drug as a demand shock with separate, measurable channels rather than one sweeping consumer thesis.',
            mechanism: 'Changed appetite or health status can affect categories through different time horizons.',
            comparison: 'Direct food effects are easier to observe than distant productivity or travel claims.',
          }),
          spending: route('healthcare spending', [
            ['Cost', 'What rises immediately?', 'Drug expenditure'],
            ['Offset', 'What might fall later?', 'Complication and chronic-care costs'],
            ['Intermediary', 'Who captures the offset?', 'Payers, patients, and providers'],
            ['Time', 'When can net savings be known?', 'After durable outcomes accumulate', 'Needs more evidence', 'warning'],
          ], {
            note: 'The buyer of the drug and the beneficiary of a later saving may be different institutions.',
            angle: 'The decisive economic question is not gross drug cost but whether the same payer can capture delayed health offsets.',
            mechanism: 'Payer turnover and benefit design connect clinical outcomes to financial value.',
            comparison: 'Societal savings and payer savings are related but not interchangeable.',
          }),
        },
      },
      question: {
        sourceLabel: 'Plain question',
        startCopy: 'You started with a question.',
        sentenceText: 'What happens when insurance stops pricing climate risk as temporary?',
        sentence: [
          'What happens when ', { route: 'insurance', text: 'insurance' }, ' stops ',
          { route: 'pricing', text: 'pricing climate risk' }, ' as ',
          { route: 'temporary', text: 'temporary' }, '?',
        ],
        routes: {
          insurance: route('insurance', [
            ['Capacity', 'Who absorbs the tail risk?', 'Insurers and reinsurers'],
            ['Constraint', 'What happens when capacity retreats?', 'Coverage narrows'],
            ['Intermediary', 'Who requires coverage?', 'Mortgage lenders'],
            ['Consequence', 'What asset is exposed next?', 'Property liquidity and value', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'Insurance can transmit physical risk into credit and property markets.',
            angle: 'The first systemic signal may be a mortgageability problem rather than a visible disaster loss.',
            mechanism: 'Coverage requirements connect underwriting capacity to mortgage eligibility and transaction liquidity.',
            comparison: 'Premium increases and coverage withdrawal have different downstream effects.',
          }),
          pricing: route('pricing climate risk', [
            ['Measure', 'What enters the premium?', 'Expected loss and uncertainty'],
            ['Update', 'What changes the estimate?', 'Claims, models, and reinsurance cost'],
            ['Response', 'Who can still afford coverage?', 'Households with unequal buffers'],
            ['Consequence', 'What follows repricing?', 'Adaptation, exit, or underinsurance', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'A price is both a risk estimate and a constraint on who can remain insured.',
            angle: 'Climate insurance is becoming an allocation mechanism: the premium determines who can stay, adapt, or exit.',
            mechanism: 'Updated loss estimates become household constraints through premiums and coverage terms.',
            comparison: 'Accurate risk pricing can improve signals while worsening affordability.',
          }),
          temporary: route('temporary', [
            ['Assumption', 'What would make the shock temporary?', 'Losses revert to an old baseline'],
            ['Contradiction', 'What if the baseline is moving?', 'Repeated hazards and rising severity'],
            ['Institution', 'Who changes behavior first?', 'Reinsurers and regulators'],
            ['Conclusion', 'What new frame follows?', 'Structural transition, not isolated volatility', 'Plausible hypothesis', 'warning'],
          ], {
            note: 'The key disagreement is whether the loss distribution returns to its previous shape.',
            angle: 'Once the baseline moves, insurance stops smoothing isolated shocks and starts governing a structural retreat.',
            mechanism: 'Repeated model updates translate a changing hazard distribution into capacity and regulatory decisions.',
            comparison: 'Temporary volatility invites repricing; structural change can trigger withdrawal.',
          }),
        },
      },
    };

    const sentence = ideaDemo.querySelector('[data-idea-sentence]');
    const routePanel = ideaDemo.querySelector('#idea-route');
    const placeholder = ideaDemo.querySelector('[data-route-placeholder]');
    const content = ideaDemo.querySelector('[data-route-content]');
    const phrase = ideaDemo.querySelector('[data-route-phrase]');
    const list = ideaDemo.querySelector('[data-route-list]');
    const branches = ideaDemo.querySelector('[data-route-branches]');
    const note = ideaDemo.querySelector('[data-route-note]');
    const evidenceLink = ideaDemo.querySelector('[data-route-evidence]');
    const selection = ideaDemo.querySelector('[data-idea-selection]');
    const angle = ideaDemo.querySelector('[data-angle-reveal]');
    const angleTitle = ideaDemo.querySelector('[data-angle-title]');
    const angleCopy = ideaDemo.querySelector('[data-angle-copy]');
    const angleActions = ideaDemo.querySelector('[data-angle-actions]');
    const followFurther = ideaDemo.querySelector('[data-follow-further]');
    const sourceButtons = [...ideaDemo.querySelectorAll('[data-source]')];
    const canHover = window.matchMedia('(hover: hover) and (pointer: fine)');
    let sourceKey = 'article';
    let activeRoute = null;
    let pinnedRoute = null;
    let previewTimer = null;
    let explored = new Set();

    const storyFields = {
      thread: document.querySelector('[data-story-thread]'),
      start: document.querySelector('[data-story-start]'),
      seed: document.querySelector('[data-story-seed]'),
      mechanism: document.querySelector('[data-story-mechanism]'),
      comparison: document.querySelector('[data-story-comparison]'),
      angle: document.querySelector('[data-story-angle]'),
      destination: document.querySelector('[data-destination-source]'),
    };

    const resetAngle = () => {
      angle.classList.remove('is-ready');
      angleTitle.textContent = 'The stronger idea appears after you inspect two paths.';
      angleCopy.textContent = 'Markov does not jump from a provocative sentence to a polished conclusion. It makes the missing mechanism and the uncertainty visible first.';
      angleActions.hidden = true;
    };

    const updateStory = (selected) => {
      const example = examples[sourceKey];
      storyFields.start.textContent = example.startCopy;
      storyFields.seed.textContent = example.sentenceText;
      storyFields.destination.textContent = example.sourceLabel;
      if (!selected) {
        storyFields.thread.textContent = 'Choose a phrase above';
        storyFields.mechanism.textContent = 'Choose an underlined phrase to expose the skipped steps.';
        storyFields.comparison.textContent = 'Support, weakness, and alternative explanations stay separate.';
        storyFields.angle.textContent = 'The conclusion cannot outrank its weakest essential connection.';
        return;
      }
      storyFields.thread.textContent = selected.phrase;
      storyFields.mechanism.textContent = selected.mechanism;
      storyFields.comparison.textContent = selected.comparison;
      storyFields.angle.textContent = selected.angle;
    };

    const revealAngle = (selected) => {
      if (explored.size < 2) return;
      angle.classList.add('is-ready');
      angleTitle.textContent = selected.angle;
      angleCopy.textContent = 'This is a stronger interpretation because the mechanism, competing path, and weakest evidence state remain attached.';
      angleActions.hidden = false;
    };

    const setExpanded = (routeName) => {
      sentence.querySelectorAll('[data-route]').forEach((trigger) => {
        trigger.setAttribute('aria-expanded', String(trigger.dataset.route === routeName));
      });
    };

    const clearRoute = () => {
      activeRoute = null;
      setExpanded(null);
      routePanel.classList.remove('has-route');
      placeholder.hidden = false;
      content.hidden = true;
      selection.textContent = 'No path selected.';
    };

    const renderRoute = (routeName, { pin = false } = {}) => {
      const selected = examples[sourceKey].routes[routeName];
      if (!selected) return;
      activeRoute = routeName;
      if (pin) {
        pinnedRoute = routeName;
        explored.add(routeName);
        updateStory(selected);
        revealAngle(selected);
      }
      setExpanded(routeName);
      routePanel.classList.add('has-route');
      placeholder.hidden = true;
      content.hidden = false;
      phrase.textContent = selected.phrase;
      list.replaceChildren();
      selected.steps.forEach((step, index) => {
        const item = document.createElement('li');
        item.className = 'route-step is-entering';
        item.style.setProperty('--step-index', index);
        const label = document.createElement('span');
        label.className = 'route-label';
        label.textContent = step[0];
        const question = document.createElement('span');
        question.className = 'route-question';
        question.textContent = step[1];
        const node = document.createElement('strong');
        node.className = 'route-node';
        node.textContent = step[2];
        item.append(label, question, node);
        if (step[3]) {
          const state = document.createElement('span');
          state.className = `route-state ${step[4] === 'evidence' ? 'is-evidence' : 'is-warning'}`;
          state.textContent = step[3];
          item.append(state);
        }
        list.append(item);
      });
      branches.replaceChildren();
      if (selected.branches) {
        selected.branches.forEach((branch) => {
          const item = document.createElement('div');
          item.className = `route-branch ${branch[2] === 'strong' ? 'is-strong' : ''}`;
          const title = document.createElement('strong');
          title.textContent = branch[0];
          const state = document.createElement('span');
          state.textContent = branch[1];
          item.append(title, state);
          branches.append(item);
        });
        branches.hidden = false;
      } else {
        branches.hidden = true;
      }
      note.textContent = selected.note;
      if (selected.evidence) {
        evidenceLink.textContent = selected.evidence[0];
        evidenceLink.href = selected.evidence[1];
        evidenceLink.hidden = false;
      } else {
        evidenceLink.hidden = true;
        evidenceLink.removeAttribute('href');
      }
      selection.textContent = routeName === pinnedRoute
        ? `${selected.phrase} pinned. Press Escape to clear the path.`
        : `Previewing ${selected.phrase}. Click to pin this path.`;
    };

    const restorePinned = () => {
      window.clearTimeout(previewTimer);
      if (pinnedRoute) renderRoute(pinnedRoute);
      else clearRoute();
    };

    const bindTriggers = () => {
      sentence.querySelectorAll('[data-route]').forEach((trigger) => {
        if (canHover.matches) {
          trigger.addEventListener('pointerenter', () => {
            window.clearTimeout(previewTimer);
            previewTimer = window.setTimeout(() => renderRoute(trigger.dataset.route), 120);
          });
          trigger.addEventListener('pointerleave', restorePinned);
        }
        trigger.addEventListener('focus', () => renderRoute(trigger.dataset.route));
        trigger.addEventListener('blur', () => window.setTimeout(() => {
          const focused = document.activeElement;
          if (sentence.contains(focused) || routePanel.contains(focused)) return;
          restorePinned();
        }, 0));
        trigger.addEventListener('click', () => renderRoute(trigger.dataset.route, { pin: true }));
      });
    };

    routePanel.addEventListener('focusout', () => window.setTimeout(() => {
      const focused = document.activeElement;
      if (sentence.contains(focused) || routePanel.contains(focused)) return;
      restorePinned();
    }, 0));

    const renderSentence = (key) => {
      const example = examples[key];
      sourceKey = key;
      activeRoute = null;
      pinnedRoute = null;
      explored = new Set();
      sentence.replaceChildren();
      example.sentence.forEach((part) => {
        if (typeof part === 'string') {
          sentence.append(document.createTextNode(part));
          return;
        }
        const trigger = document.createElement('button');
        trigger.className = 'idea-trigger';
        trigger.type = 'button';
        trigger.dataset.route = part.route;
        trigger.setAttribute('aria-expanded', 'false');
        trigger.setAttribute('aria-controls', 'idea-route');
        trigger.textContent = part.text;
        sentence.append(trigger);
      });
      sourceButtons.forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.source === key));
      });
      resetAngle();
      updateStory(null);
      clearRoute();
      bindTriggers();
    };

    sourceButtons.forEach((button, index) => {
      button.addEventListener('click', () => renderSentence(button.dataset.source));
      button.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        let nextIndex = index;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = sourceButtons.length - 1;
        if (event.key === 'ArrowRight') nextIndex = (index + 1) % sourceButtons.length;
        if (event.key === 'ArrowLeft') nextIndex = (index - 1 + sourceButtons.length) % sourceButtons.length;
        sourceButtons[nextIndex].focus();
        sourceButtons[nextIndex].click();
      });
    });

    followFurther.addEventListener('click', () => {
      if (!activeRoute) return;
      const selected = examples[sourceKey].routes[activeRoute];
      pinnedRoute = activeRoute;
      explored.add(activeRoute);
      explored.add(`${activeRoute}:further`);
      updateStory(selected);
      revealAngle(selected);
      selection.textContent = `${selected.phrase} is now the thread carried through the page.`;
      angle.scrollIntoView({ behavior: canHover.matches ? 'smooth' : 'auto', block: 'center' });
    });

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || (!activeRoute && !pinnedRoute)) return;
      pinnedRoute = null;
      clearRoute();
      updateStory(null);
    });

    bindTriggers();
    updateStory(null);
  }

  const storySteps = [...document.querySelectorAll('.idea-story-step')];
  if (storySteps.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
      if (!visible) return;
      storySteps.forEach((step) => step.classList.toggle('is-current', step === visible.target));
    }, { rootMargin: '-24% 0px -42%', threshold: [0.15, 0.4, 0.7] });
    storySteps.forEach((step) => observer.observe(step));
  }

  const landingIntake = document.querySelector('[data-landing-intake]');
  if (landingIntake) {
    landingIntake.addEventListener('submit', () => {
      const source = landingIntake.querySelector('[name="source"]');
      if (source && source.value.trim()) {
        sessionStorage.setItem('markov.pendingSource', source.value.trim());
      }
    });
  }

  const workspaceSource = document.querySelector('#source-value');
  if (workspaceSource) {
    const pendingSource = sessionStorage.getItem('markov.pendingSource');
    if (pendingSource && !workspaceSource.value) {
      workspaceSource.value = pendingSource;
      sessionStorage.removeItem('markov.pendingSource');
    }
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
