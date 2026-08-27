# The Markov dream

Status: product and experience contract, 2026-08-26

## The dream we sell

**Stand behind every sentence.**

Markov is the evidence desk for people and agents who publish consequential
work. Give it a source, question, or premise. It returns a finished Brief,
Research Report, or ready-to-record Script whose important claims can be traced
back to exact passages, timestamps, pages, and qualifications.

The customer is not buying “AI research.” They are buying the moment when a
messy, doubtful pile of tabs becomes work they can confidently brief, present,
publish, record, or send downstream to an agent.

The emotional transformation is:

```text
I think this is true  ->  I can show why this holds up
I have material      ->  I have something finished
I need to check it   ->  I know exactly what still needs judgment
```

Markov does not promise omniscience. It promises inspectability, useful
completion, and honest edges.

## Positioning

**Plain-language value proposition**

Markov helps serious creators, analysts, and research-led teams turn a question
or source into a finished brief, research report, or factual script—each
important claim linked to inspectable evidence—without living in tabs or trusting
a black box.

**Category**

An evidence-to-output platform, delivered as both:

1. a SaaS workspace for people;
2. an asynchronous API for software, automations, and agents.

This is intentionally narrower and more useful than “an AI workspace” or “an AI
search engine.” Markov owns the distance between source material and a defensible
finished artifact.

## Who it is for

**Best fit**

- factual YouTube creators, producers, and editorial teams who need a script
  they can record after one human pass;
- analysts, strategists, consultants, and operators who need a concise answer or
  professional research report with inspectable support;
- research-led marketing, policy, and communications teams that cannot afford
  confident but untraceable prose;
- developers and agent builders who need structured claims, evidence, status,
  artifacts, webhooks, and predictable asynchronous jobs.

**Poor fit**

- fiction, screenplays, ad concepts, social filler, generic SEO volume, or
  “write anything about anything” use cases;
- customers who only want a chatbot answer and do not care where it came from;
- academic ghostwriting or a promise that human editorial responsibility can be
  removed;
- private, paywalled, or inaccessible sources Markov is not authorized or able
  to inspect.

The product should say these boundaries out loud. Specificity is a trust signal.

## The two-door product

### Markov Workspace — for people

The SaaS should feel like a calm editorial instrument, not a dashboard factory.
The primary object is a research case. A customer should always know:

- what Markov is working on;
- which stage it is in;
- which claims matter;
- which evidence supports, qualifies, or contradicts them;
- what is finished;
- what remains uncertain;
- what they can do next: export, convert, deepen, revise, or request verification.

The reading experience is the product. Artifact pages use a document center,
outline rail, and evidence rail. They do not bury the finished output beneath
analytics cards or lead with a knowledge graph.

### Markov API — for software and agents

The API sells the same contract in machine-readable form. It is not a secondary
feature page or a different engine. Agents receive stable job state, stage
events, cases, claims, evidence passages, provenance, costs, artifacts, and
webhooks. Human and agent customers should be able to inspect the same IDs.

The developer promise is:

> Send one research job. Receive a finished artifact and the evidence graph
> required to audit or continue it.

## The offer

There are three outcomes, each available as Instant or Verified:

| Product | Customer buys | The job it replaces |
| --- | --- | --- |
| Brief | confident source triage and the bottom line | watching, reading, and manually checking a long source |
| Research | a defensible report and evidence packet | open-ended tab collection and a second synthesis pass |
| Script | a ready-to-record factual package | research dossier, outline, draft, and separate fact check |

Instant is agentic and transparent about unresolved uncertainty. Verified runs
the same structured case through an audited human review queue. Credits are the
shared unit for SaaS and API usage. Final prices remain configuration, not copy
or business logic.

## Primary conversion

**Primary CTA:** `Open Markov`

It truthfully routes an existing customer to the workspace login. We should not
claim a free trial or self-serve signup until those flows exist.

**Secondary CTA:** `See a finished case`

It jumps to a real, clearly labeled demonstration of the artifact, claim ledger,
and evidence rail. The demo reduces uncertainty without forcing registration.

Developer pages use `Read the API guide` as their primary CTA and `Open Markov`
as the cross-product secondary action.

## Brand character

**Primary archetype: Sage. Secondary accent: Creator.**

Markov is rigorous, calm, and exact, but the outcome is creative and usable. It
does not perform as a magical oracle, rebel against “old research,” or use fear
to manufacture urgency.

**Voice traits**

- precise;
- composed;
- candid.

**Avoid**

- breathless superlatives and words such as revolutionary, effortless, magic,
  game-changing, or supercharge;
- vague “unlock your potential” copy;
- anthropomorphizing the system as a genius that “knows everything”;
- fake certainty, fake scarcity, fake social proof, and invented metrics.

**Headline behavior**

State an outcome or useful tension in few words. Follow with a literal product
description. The homepage pairing is:

> Research you can publish.
>
> Markov turns a source, question, or premise into a finished brief, research
> report, or factual script—with every important claim linked to evidence you
> can inspect.

**Visual behavior**

- editorial, archival, and technical rather than futuristic;
- warm paper, deep ink, mineral green, and one sharp signal color;
- a serif display face paired with a neutral system sans and mono for evidence
  IDs;
- strong rules, margins, tabs, annotations, and document composition;
- product UI, passages, timestamps, and claim status as imagery;
- restrained radii and shadow; not every block is a floating card;
- motion only when it communicates state or relationship, with reduced-motion
  support.

**The anti-slop list**

Do not use purple/blue aurora gradients, glowing orbs, abstract AI brains,
floating glass cards, stock people looking at laptops, dozens of pills, fake
customer-logo walls, ungrounded productivity percentages, or three-column icon
grids that could belong to any SaaS.

## Landing-page narrative

The public page should answer the five-second test before any interaction:

1. **Hero:** “Research you can publish,” a literal sentence describing the three
   outputs and evidence, `Open Markov`, `See a finished case`, and a truthful
   product composition.
2. **The dream:** contrast “another answer” with “a finished case you can stand
   behind.”
3. **Product proof:** show a Brief in the center with claim status, exact source
   locator, and evidence in the rail.
4. **Three outcomes:** Brief, Research, Script, framed as jobs completed rather
   than feature bundles.
5. **How it works:** Source -> claims -> evidence -> finished artifact, with
   uncertainty preserved.
6. **Two doors:** Workspace for people and API for agents, visibly connected to
   the same research case.
7. **Fit and boundaries:** explicit best-for and not-for statements.
8. **Trust:** only product facts that exist today—inspectable passages, additive
   history, owner boundaries, structured review—not invented testimonials.
9. **Final CTA:** repeat `Open Markov` with the promise in context.

Pricing and developer documentation are first-class pages, not footer afterthoughts.

## SaaS information architecture

```text
Public
  Home
  Product
  Pricing
  Developers
  Sign in

Workspace
  Overview
  New research
  Projects
  Usage and credits
  API access

Research case
  Processing timeline
  Finished artifacts
  Sources and locators
  Claim ledger
  Research gaps

Artifact reader
  Outline | finished document | evidence rail
  Export | Convert | Deepen | Revise | Review status

Internal
  Verified review queue
  Structured claim/evidence decisions
  Finalize delivery
```

The first implementation may combine Overview and New research, but navigation
and page language should make the complete SaaS model visible.

## UX rules

1. Lead with the customer’s artifact, not the engine.
2. One primary action per page.
3. Prefer meaningful state language: “Finding evidence for C4” over “Processing.”
4. Show evidence beside the claim it affects.
5. Keep uncertainty visible without turning the UI into a warning dashboard.
6. Reveal advanced constraints progressively after mode selection.
7. Preserve the user’s place when they deepen or revise.
8. Never make a conversion look like a new project; it is another view of the
   same case.
9. Make keyboard focus, touch targets, contrast, zoom, and reduced motion part of
   the visual system.
10. Design the empty, loading, failed, awaiting-review, and completed states as
    deliberately as the happy path.

## Research notes behind the direction

- GOV.UK's current design principles start with user needs, advise doing less,
  and ask teams to do the hard work to make services simple. That supports an
  outcome-led flow over a feature-heavy AI dashboard:
  https://www.gov.uk/guidance/government-design-principles
- Linear's current homepage names its category and audience in the hero and puts
  recognizable product state immediately beneath it. The lesson is “show the
  system,” not “copy the dark aesthetic”: https://linear.app/
- Elicit pairs a plain category statement with a workflow demo, authentic case
  studies, transparent accuracy claims, and sentence-level citations. Markov
  should adopt the proof adjacency and reject unsupported scale claims:
  https://elicit.com/
- Stripe describes major product pages as stories while repeatedly emphasizing
  performance, accessibility, and fallback behavior. Markov should earn visual
  distinction through product-specific composition, not decorative weight:
  https://stripe.com/blog/connect-front-end-experience
- W3C's WCAG 2.2 update adds explicit focus and target-size requirements. These
  are baseline product quality, not polish:
  https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- Current Core Web Vitals “good” thresholds are LCP <= 2.5s, INP <= 200ms, and
  CLS <= 0.1 at the 75th percentile. The page should use server-rendered HTML,
  local/system fonts, small CSS, and minimal JavaScript:
  https://web.dev/articles/defining-core-web-vitals-thresholds

## Proof inventory

**Truthfully available now**

- runnable Brief, Research, and Script renderers;
- shared research cases and cross-mode conversion;
- stored timestamps, pages, sections, claims, evidence passages, stances, and
  rationale;
- Instant and Verified states with structured reviewer decisions;
- asynchronous API, idempotency, webhooks, owner isolation, credits, Stripe
  hooks, costs, and usage events;
- network-free acceptance fixture and representative sample artifacts.

**Not available; do not imply**

- customer counts, time saved, revenue impact, logos, testimonials, or case-study
  metrics;
- self-serve signup or a free trial;
- distributed job workers or enterprise identity administration;
- SOC 2, HIPAA, GDPR certification claims, or guaranteed source coverage;
- accuracy percentages based on a production evaluation set.

Until real proof exists, the product itself is the proof. Show the evidence
packet, the exact locator, the decision trail, and the finished artifact.

## Success criteria

The experience is successful when a qualified visitor can answer these after
five seconds:

1. Markov creates finished research-backed outputs.
2. It is for people or agents publishing factual work.
3. Its difference is inspectable evidence, not just citations or prose.
4. The next action is to open the workspace or examine a finished case.

And when a customer uses the SaaS, they should feel the dream directly:

> I know what holds up, what does not, and what I can ship now.
