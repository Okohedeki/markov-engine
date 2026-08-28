# Markov UI direction

Status: working product and art-direction contract, 2026-08-27
Applies to: public site, workspace intake, job progress, artifact reader, and API surfaces

## Product surface boundary

- **V1 is web-first.** The complete research, connection exploration, revision,
  review, and artifact experience belongs in the web workspace.
- **Mobile is capture, not a second workspace.** Its job is to send a link,
  selection, or question to Markov from the browsing context and sync that new
  trail to the web workspace for continued work.
- Public pages remain responsive and their demonstration remains tappable, but
  product copy must not imply that the full V1 workspace is a mobile app.

## Landing conversion brief

- **Best fit:** a creator, analyst, researcher, or agent operator who has found
  one consequential source or question and needs to understand it, test the
  missing links, and turn the strongest defensible angle into finished work.
- **Poor fit:** someone seeking an uninspectable instant answer, a generic
  association graph, or a complete phone-native research and editing workspace.
- **Positioning:** Markov helps evidence-conscious creators and analysts turn one
  source into an original, inspectable brief, research path, or script without
  losing the claims, mechanisms, uncertainty, or provenance along the way.
- **Primary conversion:** experience the phrase-driven chain, then sign in and
  follow the visitor's own source into the Markov web workspace. Static previews
  route to a truthful product demonstration until hosted account access is live.
- **Proof available now:** six interactive starting formats—YouTube, TikTok,
  articles, PDFs, audio, and questions—feeding the same research journey. The
  initial Japan and Treasury-demand example begins with a real Oxford research
  video and visibly produces a mechanism chain, a competing-path comparison,
  and brief, analysis, and script artifacts. A substantial output reader near
  the final intake shows the actual sections, fact notes, caveats, competing
  path, and ready-to-record copy a customer receives. No customer, revenue, or
  outcome claims are implied.
- **Product hierarchy:** Markov is a SaaS workspace for people first. The API
  exposes the same research chains to agents and programmatic services; it is a
  second access surface, not the product's identity.
- **Brand archetype:** Sage first, Creator second. The voice is calm, exact, and
  curious. Motion reveals reasoning; it does not decorate. Avoid omniscient AI
  language, breathless transformation claims, and faux-academic costume.

## The progress we sell

**Functional progress** — turn a source or question into an understood claim,
an evidence-backed connection, and finished work without rebuilding the research
trail for every output.

**Emotional progress** — replace the uneasy feeling of “this sounds right” with
the calm of knowing what holds up, what is interpretation, and what to check next.

**Social progress** — help a creator, analyst, or agent produce work that feels
original and can withstand a skeptical editor, collaborator, or audience.

**Dream** — every interesting thing becomes a starting point. Over time, the user
develops a body of connected, inspectable thinking instead of a pile of summaries
and forgotten tabs.

**Triggering moment** — “I found something interesting. Catch me up, show me where
it leads, or help me turn it into something I can publish.”

## Art-direction contract

### Design thesis

Markov should feel like a live line of inquiry: quiet enough to read, structured
enough to trust, and visibly capable of carrying one source through evidence and
connections into finished work.

### Memory hook

**The source trail.** A continuous indigo line links the starting source, claim,
missing assumption, connection, insight, and output. It is not a decorative node
graph. Every stop explains what changed and keeps its evidence level attached.

### Composition

- Use a strong vertical journey rather than a generic sequence of marketing
  sections.
- Give the source trail the largest canvas. On desktop, pair the trail with a
  sticky explanation or finished-output pane. On narrow landing-page viewports,
  recompose the demonstration as one readable line; do not imply that this is
  the full mobile product workspace.
- Use wide, quiet fields and thin rules. Reserve containers for interactive or
  inspectable objects, not every paragraph.
- Treat the three jobs as turns the same research can take, not three equal
  feature cards.
- In the application, keep the universal input dominant and recent work
  subordinate. In the artifact reader, keep the finished document dominant.

### Typography

- Use the existing local/system sans stack. Display type is large, compact, and
  literal; body type is calm and readable; labels and evidence metadata are
  smaller but never cryptic.
- Keep long-form measure near 65–72 characters. Use sentence case for statuses
  and actions.
- Monospace is reserved for machine-facing identifiers and code—not brand tone.

### Color logic

- Dominant field: cool near-white with white reading surfaces and deep ink.
- Primary accent: indigo, used for the active path and primary action.
- Semantic colors: green for established evidence, amber for interpretation,
  and restrained red only for contradiction or failure.
- Do not use gradients. Color must identify state, relationship, or action.

### Material language

- Research trails, source fragments, annotation gutters, underlines, rules, and
  attached evidence labels.
- Borders are mostly one-pixel dividers. Radius and shadow appear only where an
  object can be opened, selected, or moved through.
- Motion communicates a branch or state change and must respect reduced motion.

### Forbidden defaults

- Hero copy beside a fake dashboard.
- Three identical feature cards as the product story.
- Decorative network graphs, auroras, blobs, sparkles, glass, or stock people.
- Fake customer proof, case IDs, evidence, metrics, or a hosted-product CTA that
  routes to installation instructions.
- A tasteful editorial, terminal, or brutalist costume disconnected from the
  source-to-output behavior.

## Reference principles

The direction uses references as evidence rather than as templates:

1. **Elicit systematic review** — show a consequential research workflow as
   explicit stages with criteria and visible decisions. Markov should similarly
   expose how a source becomes a defensible outcome, while keeping its broader
   creator and analyst audience.
   <https://elicit.com/blog/systematic-review/>
2. **Harry Beck's Underground diagram** — simplify geography to make the
   relationship and route legible. Markov's trail should prioritize intellectual
   sequence over a literal force-directed graph.
   <https://library.ltmuseum.co.uk/portal/Default/en-GB/RecordView/Index/106>
3. **GOV.UK step-by-step navigation** — ordered stages are useful when the order
   helps the task, and choices should be written as explicit “and/or” branches.
   Markov should use ordered work stages for processing and clear branches for
   Catch up, Explore, or Script.
   <https://design-system.service.gov.uk/patterns/step-by-step-navigation/>

## Public story

The public page should move through one continuous proof:

```text
Found something
→ paste it or ask a question
→ isolate the important claim
→ reveal what the source leaves out
→ follow an evidence-backed connection
→ label the resulting insight honestly
→ leave with a brief, research path, or finished script
```

The first viewport must name the accepted inputs, the transformation, the three
possible outcomes, and the next truthful action. The complete source trail—not a
feature grid—is the proof. Public language must sell the persistent web workspace:
capture, parse, store, inspect, review, edit, and create. Static previews must use
**Product demo** rather than implying that hosted account access is already live.

The landing demonstration keeps six recognizable source formats visible while
showing that each becomes the same kind of inspectable research chain. Its
four-step proof alternates the action and concrete artifact across one vertical
line: captured source media, exposed mechanism, compared paths, and usable brief,
report, and script excerpts. The initial YouTube path embeds the actual Oxford
talk used as the starting source. The customer-facing sequence names the two
middle turns “Markov started a chain” and “Markov absorbed the chains,” then
shows the full artifact reader before the final intake. It does not add a
separate “current thread” status block. The people/API access bridge follows the
“Your turn” intake so the interactive conversion remains the page's culminating
action.

The first production artifact packs should cover three different reasoning jobs:

1. Japan's aging population, domestic yields, institutional portfolios, and
   U.S. Treasury demand.
2. GLP-1 drugs, food purchasing, adherence, and second-order consumer effects.
3. Nuclear project timelines, life extensions versus new builds, and near-term
   climate targets.

Each pack should contain one downloaded video or audio clip, one primary report
or PDF, one structured data source, and one credible competing analysis. Supplied
files replace representative preview media without changing the chain or output
layout.

## Application behavior

- Start with one universal source/question field.
- Let the user choose Catch up, Explore, or Script immediately after the source.
- Reveal mode-specific controls only after the user chooses that job.
- Describe progress in human language: reading, finding claims, filling context,
  checking evidence, following connections, and building the output.
- Put the finished answer first. Evidence and graph structure are inspectable
  supporting layers.
- Show why a connection matters, what supports it, where it may break, and what
  the user can do next.
- Design loading, empty, failed, review, and completed states with the same
  clarity as the happy path.

## Current product priorities

- Keep the web application—not the API or repository—as the primary product in
  navigation, copy, and calls to action.
- Show the final brief, report, answer, or script growing from the same inspected
  chain instead of presenting creation as a detached generation step.
- Make stored trails, review, versioned editing, and reuse feel like one continuous
  workspace rather than a collection of administrative screens.
- Treat mobile as frictionless browsing capture that syncs to the web workspace,
  never as a compressed version of the full product.

## Acceptance checks

- Without the Markov name, the page still reads as source → evidence → connection
  → finished work.
- A visitor understands the accepted input, useful output, and truthful next
  action within five seconds.
- Desktop carries the complete product interaction. Narrow landing-page
  viewports preserve the demonstration without overflow or illegible metadata;
  mobile product capture hands continued work back to the web workspace.
- Keyboard users can operate every tab, job choice, and disclosure with visible
  focus; reduced-motion behavior remains intact.
- Real content and explicit uncertainty survive every breakpoint.
- A second rendered pass is materially better than the first.
