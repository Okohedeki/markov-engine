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
      japan: {
        sourceLabel: 'Financial Times film',
        startCopy: 'You started with a YouTube video.',
        sentenceText: 'Why would Japanese investors sell U.S. Treasuries?',
        defaultRoute: 'sell',
        scriptOpening: 'Japan did not wake up and decide to dump America’s debt. The real story is a slower repricing of where its largest investors put their money.',
        media: {
          kind: 'youtube',
          title: 'Japan’s population crisis reaches tipping point',
          meta: 'YouTube · Financial Times film · 20 min',
          embed: 'https://www.youtube-nocookie.com/embed/nmdujC0MUKA',
          href: 'https://www.youtube.com/watch?v=nmdujC0MUKA',
        },
        sources: [
          ['FT Film: Japan’s population crisis', 'Demographic context', 'https://www.youtube.com/watch?v=nmdujC0MUKA'],
          ['Mark Yusko: Japan showed us the playbook', 'TikTok · macro thesis', 'https://www.tiktok.com/@scottmelkerwolf/video/7677675462264409357'],
          ['U.S. Debt, Japanese Yen and Your Retirement?', 'Podcast thesis · commentary', 'https://podcasts.apple.com/us/podcast/u-s-debt-japanese-yen-and-your-retirement/id1761667964?i=1000785502708'],
          ['Japan’s pension pivot', 'Reuters · live policy catalyst', 'https://www.reuters.com/world/asia-pacific/takaichis-pension-pivot-seeks-reverse-abe-era-outpouring-japanese-capital-2026-07-10/'],
          ['What about Japan?', 'NBER · rates and hedging mechanism', 'https://www.nber.org/system/files/chapters/c15418/revisions/c15418.rev0.pdf'],
        ],
        sentence: [
          'Why would ',
          { route: 'investors', text: 'Japanese investors' },
          ' ',
          { route: 'sell', text: 'sell' },
          ' ',
          { route: 'treasuries', text: 'U.S. Treasuries' },
          '?',
        ],
        routes: {
          investors: route('Japanese investors', [
            ['Actor', 'Who can actually change the allocation?', 'GPIF, insurers, banks, and private funds'],
            ['Constraint', 'Do they face the same incentives?', 'Different liabilities, mandates, and hedge policies'],
            ['Decision', 'What does each institution compare?', 'Domestic assets versus hedged foreign returns'],
            ['Test', 'What evidence would show a real move?', 'Sector-level flows—not a national headline', 'Required distinction', 'warning'],
          ], {
            branches: [
              ['Japan as one coordinated seller', 'Not established', ''],
              ['Institution-specific rebalancing', 'Evidence-compatible', 'strong'],
            ],
            note: '“Japan” compresses institutions with different balance sheets into a single actor.',
            evidence: ['Inspect the NBER public-sector balance-sheet analysis', 'https://www.nber.org/system/files/chapters/c15418/revisions/c15418.rev0.pdf'],
            angle: 'The better question is which Japanese balance sheet would sell, under which mandate, and at what hedge cost.',
            mechanism: 'Pension funds, insurers, banks, households, and the central bank do not make one synchronized portfolio decision.',
            comparison: 'Institution-specific rebalancing is plausible; a coordinated national selloff is not established.',
          }),
          sell: route('sell', [
            ['Catalyst', 'What changed now?', 'A proposal to steer pension capital home'],
            ['Relative return', 'Why reconsider foreign bonds?', 'Higher Japanese government-bond yields'],
            ['Friction', 'What erodes the dollar yield?', 'Costly USD/JPY currency hedging'],
            ['Portfolio action', 'What could institutions do?', 'Buy fewer foreign bonds or rebalance gradually', 'Stronger interpretation', 'evidence'],
          ], {
            branches: [
              ['A sudden Treasury dump', 'Not demonstrated', ''],
              ['Gradual capital repatriation', 'Stronger path', 'strong'],
            ],
            note: 'The Reuters catalyst is a policy proposal. It does not yet establish the size, timing, or instruments of any sale.',
            evidence: ['Inspect the Reuters policy report', 'https://www.reuters.com/world/asia-pacific/takaichis-pension-pivot-seeks-reverse-abe-era-outpouring-japanese-capital-2026-07-10/'],
            angle: 'The near-term story is not demographics forcing a dump; it is domestic yields and policy changing the relative appeal of overseas assets.',
            mechanism: 'Policy direction, higher JGB yields, and FX-hedging costs can make repatriation rational for specific portfolios.',
            comparison: 'Gradual capital repatriation has a visible mechanism; a sudden Treasury dump does not yet have confirming flow data.',
          }),
          treasuries: route('U.S. Treasuries', [
            ['Asset scope', 'Does “foreign assets” mean Treasuries?', 'No—foreign bonds, equities, and other holdings differ'],
            ['Transmission', 'How could rebalancing reach the U.S.?', 'Lower marginal demand or outright bond sales'],
            ['Observation', 'What must be measured?', 'Holder-level flows and Treasury transaction data'],
            ['Limit', 'What do these sources prove today?', 'A mechanism and catalyst—not a completed selloff', 'Needs confirmation', 'warning'],
          ], {
            branches: [
              ['Foreign-asset shift equals Treasury sale', 'Category error', ''],
              ['Treasury demand may weaken at the margin', 'Defensible inference', 'strong'],
            ],
            note: 'A shift toward Japanese assets could come from new contributions, equities, other foreign bonds, or Treasuries. The instrument mix remains open.',
            evidence: ['Inspect U.S. Treasury holdings data next', 'https://ticdata.treasury.gov/Publish/slt_table5.html'],
            angle: 'Watch which assets move before turning a broad repatriation thesis into a Treasury-specific claim.',
            mechanism: 'The Treasury-market effect depends on which institutions rebalance, what they own, and whether they sell or simply stop adding.',
            comparison: 'Weaker marginal Treasury demand is a defensible implication; an observed Treasury selloff still needs holder-level flow evidence.',
          }),
        },
      },
      nuclear: {
        sourceLabel: 'IEA analysis',
        startCopy: 'You started with an article.',
        sentenceText: 'Nuclear power is too slow to matter for near-term climate targets.',
        defaultRoute: 'targets',
        scriptOpening: 'The nuclear argument is framed as a race. The real constraint is the order in which replacement capacity arrives.',
        media: {
          kind: 'article',
          title: 'Nuclear Power in a Clean Energy System',
          meta: 'IEA analysis · saved article',
          detail: 'Long lead times, lifetime extensions, and near-term emissions targets',
        },
        sources: [
          ['IEA: Nuclear Power in a Clean Energy System', 'Lead times, investment, and life extensions', 'https://www.iea.org/reports/nuclear-power-in-a-clean-energy-system'],
          ['IAEA Power Reactor Information System', 'Reactor milestones and operating history', 'https://pris.iaea.org/pris/'],
          ['U.S. EIA Electric Power Annual', 'Observed nuclear capacity factors', 'https://www.eia.gov/electricity/annual/table.php?t=epa_04_08_b.html'],
        ],
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
        defaultRoute: 'hollowing',
        scriptOpening: 'The offices emptied first. The fiscal shock may not arrive until years later.',
        media: {
          kind: 'tiktok',
          title: 'Remote work is hollowing out city tax bases',
          meta: 'TikTok · 00:10 saved clip',
          detail: 'A fast claim with the causal steps still missing',
        },
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
        defaultRoute: 'reduce',
        scriptOpening: 'A heat pump is not automatically clean. Its value changes hour by hour with the fuel it replaces and the power it draws.',
        media: {
          kind: 'pdf',
          title: 'Heat pumps and household emissions',
          meta: 'PDF · page 18 saved',
          detail: 'Seasonal performance, marginal power, and the displaced heating fuel',
        },
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
      glp1: {
        sourceLabel: 'Podcast excerpt',
        startCopy: 'You started with a podcast.',
        sentenceText: 'Weight-loss drugs may reshape more than healthcare spending.',
        defaultRoute: 'reshape',
        scriptOpening: 'Weight-loss drugs may be a consumer-demand shock hiding inside a healthcare story.',
        media: {
          kind: 'audio',
          title: 'The second-order effects of GLP-1 drugs',
          meta: 'Podcast · 31:42 saved moment',
          detail: 'Food demand, adherence, access, and downstream industries',
        },
        sources: [
          ['JAMA: Consumer Food Purchases After GLP-1 Initiation', 'Observed changes in supermarket baskets', 'https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2844224'],
          ['Marketing Science: The No-Hunger Games', 'Household grocery and restaurant spending', 'https://journals.sagepub.com/doi/10.1177/00222437251412834'],
          ['KFF Health Tracking Poll', 'Use, access, affordability, and persistence', 'https://www.kff.org/health-costs/kff-health-tracking-poll-may-2024-the-publics-use-and-views-of-glp-1-drugs/'],
        ],
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
        defaultRoute: 'pricing',
        scriptOpening: 'Climate risk enters the housing market before the disaster—through the price and availability of insurance.',
        media: {
          kind: 'question',
          title: 'What happens when insurance stops pricing climate risk as temporary?',
          meta: 'Question · captured in Markov',
          detail: 'A starting point for a new research chain',
        },
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

    const japanVariant = ({ sourceLabel, startCopy, media }) => ({
      ...examples.japan,
      sourceLabel,
      startCopy,
      media,
    });

    examples.article = japanVariant({
      sourceLabel: 'Reuters analysis',
      startCopy: 'You started with an article.',
      media: {
        kind: 'article',
        title: 'Japan’s pension pivot puts overseas capital in play',
        meta: 'Reuters · July 10, 2026',
        detail: 'Japan’s finance minister proposed increasing domestic allocations at the $1.8 trillion GPIF and other retirement funds. Implementation details remain unsettled.',
        href: 'https://www.reuters.com/world/asia-pacific/takaichis-pension-pivot-seeks-reverse-abe-era-outpouring-japanese-capital-2026-07-10/',
      },
    });
    examples.tiktok = japanVariant({
      sourceLabel: 'TikTok video',
      startCopy: 'You started with a TikTok.',
      media: {
        kind: 'tiktok',
        title: 'Mark Yusko: Japan showed us the playbook',
        meta: 'TikTok · The Wolf Of All Streets · 54 sec',
        embed: 'https://www.tiktok.com/player/v1/7677675462264409357?music_info=1&description=1&autoplay=0',
        href: 'https://www.tiktok.com/@scottmelkerwolf/video/7677675462264409357',
      },
    });
    examples.pdf = japanVariant({
      sourceLabel: 'NBER paper',
      startCopy: 'You started with a paper.',
      media: {
        kind: 'pdf',
        title: 'What about Japan?',
        meta: 'NBER · Chien, Cole & Lustig · March 2026',
        detail: 'A public-sector balance-sheet analysis of low rates, duration risk, foreign assets, and currency hedging.',
        preview: 'static/japan-nber-cover.png',
        href: 'https://www.nber.org/system/files/chapters/c15418/revisions/c15418.rev0.pdf',
      },
    });
    examples.podcast = japanVariant({
      sourceLabel: 'Retirement podcast',
      startCopy: 'You started with a podcast.',
      media: {
        kind: 'audio',
        title: 'U.S. Debt, Japanese Yen and Your Retirement?',
        meta: 'Apple Podcasts · 25 min',
        detail: 'A market thesis connecting Japanese Treasury demand with U.S. rates, markets, and retirement planning.',
        href: 'https://podcasts.apple.com/us/podcast/u-s-debt-japanese-yen-and-your-retirement/id1761667964?i=1000785502708',
      },
    });
    examples.question = japanVariant({
      sourceLabel: 'Research question',
      startCopy: 'You started with a question.',
      media: {
        kind: 'question',
        title: 'Why would Japanese investors sell U.S. Treasuries?',
        meta: 'Question · entered in Markov',
        detail: 'Separate the actors, establish whether a sale occurred, and trace the mechanism before accepting the premise.',
      },
    });
    delete examples.nuclear;
    delete examples.glp1;

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
    const followFurther = ideaDemo.querySelector('[data-follow-further]');
    const sourceButtons = [...ideaDemo.querySelectorAll('[data-source]')];
    const canHover = window.matchMedia('(hover: hover) and (pointer: fine)');
    let sourceKey = 'article';
    let activeRoute = null;
    let pinnedRoute = null;
    let previewTimer = null;

    const storyFields = {
      start: document.querySelector('[data-story-start]'),
      seed: document.querySelector('[data-story-seed]'),
      sourceArtifact: document.querySelector('[data-story-source-artifact]'),
      mechanismNodes: document.querySelector('[data-story-mechanism-nodes]'),
      mechanism: document.querySelector('[data-story-mechanism]'),
      comparisonRows: document.querySelector('[data-story-comparison-rows]'),
      comparison: document.querySelector('[data-story-comparison]'),
      destination: document.querySelector('[data-destination-source]'),
    };

    const renderSourceArtifact = (media) => {
      const mediaId = `${media.kind}:${media.title}`;
      if (storyFields.sourceArtifact.dataset.mediaId === mediaId) return;
      storyFields.sourceArtifact.replaceChildren();
      storyFields.sourceArtifact.dataset.mediaId = mediaId;
      if (media.kind === 'youtube' || media.kind === 'tiktok') {
        const frame = document.createElement('iframe');
        frame.loading = 'lazy';
        frame.src = media.embed;
        frame.title = `${media.title} — ${media.meta}`;
        frame.dataset.platform = media.kind;
        frame.allow = media.kind === 'youtube'
          ? 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share'
          : 'fullscreen';
        frame.allowFullscreen = true;
        storyFields.sourceArtifact.append(frame);
      } else if (media.kind === 'pdf') {
        const preview = document.createElement('a');
        preview.className = 'pdf-preview';
        preview.href = media.href;
        preview.target = '_blank';
        preview.rel = 'noreferrer';
        const image = document.createElement('img');
        image.src = media.preview;
        image.alt = `First page of ${media.title}`;
        image.loading = 'lazy';
        image.width = 1220;
        image.height = 1582;
        const open = document.createElement('span');
        open.textContent = 'Open the full PDF ↗';
        preview.append(image, open);
        storyFields.sourceArtifact.append(preview);
      } else {
        const preview = document.createElement(media.href ? 'a' : 'div');
        preview.className = `source-preview is-${media.kind}`;
        if (media.href) {
          preview.classList.add('source-preview-link');
          preview.href = media.href;
          preview.target = '_blank';
          preview.rel = 'noreferrer';
        }
        const kind = document.createElement('span');
        kind.className = 'source-preview-kind';
        kind.textContent = media.kind;
        const title = document.createElement('strong');
        title.textContent = media.title;
        const detail = document.createElement('p');
        detail.textContent = media.detail;
        preview.append(kind, title, detail);
        if (media.href) {
          const open = document.createElement('span');
          open.className = 'source-preview-open';
          open.textContent = 'Open original ↗';
          preview.append(open);
        }
        storyFields.sourceArtifact.append(preview);
      }
    }
  });
})();
