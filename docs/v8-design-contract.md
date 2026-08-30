# Markov V8 — clean-slate interface contract

Status: active UI/UX direction, 2026-08-30  
Scope: public site, workspace, case reader, supporting product pages, and internal review surfaces

This contract replaces every earlier visual implementation. The engine, routes,
data model, evidence behavior, and customer jobs remain; the accumulated V3–V7
component and styling language does not.

## Product brief

- **Problem:** A research-led creator or analyst needs a way to keep developing a
  source because summaries stop before the missing context, defensible
  connection, and usable original angle appear.
- **Primary outcome:** Start with one source or question and leave with a brief,
  research path, or factual script whose evidence and uncertainty remain attached.
- **Best fit:** research-led creators, editorial teams, analysts, strategists,
  and agent builders producing factual work.
- **Poor fit:** generic high-volume copy, unconstrained fiction, passive
  bookmarking, or work where provenance does not matter.
- **Primary public action:** `Open the workspace` (sign-in is the truthful next
  step). The lower-commitment action is `See one source unfold`.
- **Brand character:** Sage first, Creator second. Voice is plain, alert, and
  candid—never mystical, breathless, or faux-academic.

## Progress being sold

- **Functional:** one input becomes understood claims, checked context, useful
  connections, and finished work without rebuilding the trail.
- **Emotional:** uncertainty becomes a visible next question instead of an
  anxious pile of tabs.
- **Social:** the user can publish a point of view that is original and can be
  defended under scrutiny.
- **Dream:** every worthwhile encounter can keep developing until it becomes
  useful work.

## Art-direction contract

### Design thesis

Markov is a **curiosity instrument**: crisp and legible like a serious research
tool, but alive with small moments of discovery as one source opens into several
routes and tightens back into finished work.

### Memory hook

**The living thread.** One unmistakable line leaves the starting source, bends
through a missing assumption, forks into named research routes, and stitches
itself into the margin of the finished document. It is always attached to words
that explain what changed; it is never a decorative network graph.

### Composition

- The public first viewport is one full-canvas composition: a direct promise, a
  universal source dock, and the opening section of the living thread. There is
  no hero beside a dashboard screenshot.
- The public proof is one continuous source-to-output journey. Scale and rhythm
  change at each turn so the page does not feel like a stack of equal sections.
- The product app begins with current work. Capture is always reachable but does
  not occupy the page.
- Case pages use `Explore`, `Output`, and `Sources`. Explore shows a starting
  source becoming readable branches; Output becomes a quiet document; Sources
  become a scan-friendly provenance table.
- Desktop uses broad horizontal working planes. Mobile is deliberately
  recomposed around capture, resume, and the next decision—not a shrunken desk.

### Typography

- System sans (`Segoe UI Variable`, `Aptos`, and platform fallbacks) carries the
  interface with high contrast between compact labels and decisive headings.
- A system serif appears only inside finished document excerpts, so the change
  in type signals that research has become authored work.
- Display copy is literal and compact. Data uses tabular numerals. Monospace is
  reserved for locators, source types, and machine-facing identifiers.

### Color logic

- **Canvas:** a cool, almost-white mist that keeps long sessions calm.
- **Ink:** blue-black for primary reading and a softer slate for context.
- **Thread:** vivid ultramarine for the active path and primary action.
- **Discovery:** electric citron appears only when Markov reveals a useful turn.
- **Evidence:** spruce means supported; amber means qualified; vermilion means
  contradiction or failure.
- No gradients. Color always means action, relationship, or evidence state.

### Material language

- Source docks, clipped excerpts, route lines, margin notes, locators, annotated
  documents, and decision ledgers.
- Rules organize; containers appear only for interactive or inspectable objects.
- Corners are modest. Shadows are reserved for menus, dialogs, and an object
  that is visibly in motion.
- Motion explains continuity: the source dock acknowledges capture, the active
  route draws forward, and switching outputs moves the same evidence margin.
  Reduced motion reveals the same state immediately.

### Interaction thesis

1. Selecting a starting format rewrites the dock in place and returns focus to
   the input; the control feels ready rather than blank.
2. Choosing a research route updates the mechanism, evidence state, and possible
   output together so the user understands the consequence of the choice.
3. A small progress pulse moves only while work is active; stopping, failure,
   and completion use explicit text and never rely on color alone.

### Forbidden defaults

- Old `v3`, `v4`, `v5`, `v6`, or `v7` classes and layered stylesheets.
- A hero/dashboard split, generic card grid, decorative node graph, fake
  terminal, glass, glow, gradient, blob, stock person, or abstract AI artwork.
- Oversized raw model output, unbounded titles, and engine vocabulary in the
  customer hierarchy.
- Fake customers, metrics, confidence, evidence, source IDs, or hosted access.
- A mobile bottom bar that covers content, tiny desktop rails, or hover-only
  disclosure.

## Content sequence

### Public

1. Start with almost anything.
2. Watch one real source unfold into substance, missing context, and a connection.
3. Compare three defensible directions without hiding their weak points.
4. Turn the selected route into a brief, research report, or factual script.
5. State fit and limits plainly.
6. Open the workspace.

### Workspace

1. Resume work that needs a decision.
2. See active research in human stage language.
3. Capture a new source or question.
4. Reopen recent Chains and finished outputs.

### Case

1. Read the starting source and live question.
2. Explore a small number of ranked routes.
3. Inspect the support, weakness, and supplemental sources beside each route.
4. Shape an output with explicit audience, angle, length, and evidence boundary.
5. Read and revise the output with evidence attached.

## Required states

- Public navigation open/closed; source and output selection; visible focus;
  reduced motion.
- Workspace populated, empty, processing, ready, failed, and capture-disabled.
- Case explore/output/sources views; empty routes; missing evidence; dialog open,
  close, validation, and focus restoration.
- Authentication error; reviewer queue empty; review decision forms; export
  entitlements; global error recovery.

## Acceptance checks

- In five seconds a visitor can name the accepted input, the three outputs, the
  evidence-linked difference, and the next action.
- Removing the Markov name still leaves a recognizable source → missing context
  → route → finished document journey.
- A returning customer sees the next decision before account or usage metadata.
- Dynamic titles and findings clamp or wrap without taking over the page.
- Desktop (`1440 × 900`), tablet (`1024 × 768`), and mobile (`390 × 844`) have no
  overflow, clipped controls, covered content, or illegible metadata.
- Keyboard navigation, visible focus, semantic landmarks, status announcements,
  44px touch targets, and reduced-motion behavior are present.
- A rendered second pass materially improves the first.
