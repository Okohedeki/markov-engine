# Chain workspace UX contract

Status: implementation contract, 2026-08-29

## Product correction

The current artifact reader makes Markov look like a fact-analysis product. The
workspace must instead show that a source is the first node in a growing body of
work. Verification supports that journey, but is not the journey itself.

The primary loop is:

```text
starting source
→ important claim
→ missing context or open question
→ supplemental sources
→ competing paths
→ an idea worth developing
→ a guided brief, analysis, or script
```

The full claim ledger remains available as provenance. It does not define the
main navigation or visual hierarchy.

## Engine delta behind this redesign

The YouTube V2 work changed four production engine modules substantially:
`evidence.py`, `extract.py`, `planning.py`, and `renderers.py`. From the first
caption-collapse checkpoint through the latest evidence correction, the diff is
1,286 insertions and 99 deletions, plus a 440-line reproducible evaluation
runner and new tests.

The evidence layer alone gained 185 lines and removed 13. Those changes improved
off-topic filtering and claim entailment, but also made retrieval conservative.
The UI cannot repair thin discovery by dressing evidence statuses more clearly.
It must expose supplemental sources, open questions, and proposed paths so the
user can decide which branch deserves another research pass.

## Art-direction contract

### Design thesis

Markov should feel like a working table where one source opens several legible
routes: calm enough for long reading, but visibly unfinished wherever the user
can ask the next question or make the next artifact.

### Memory hook

**The open branch.** Each promising research gap leaves the starting source on a
visible line, gathers supplemental material along the way, and ends in a named
choice: research it, save it, or shape an output from it.

### Composition

- Keep the existing web-app shell and system typography.
- Replace the artifact-first three-column reader with one case workspace and
  three explicit views: `Explore`, `Output`, and `Sources`.
- Make `Explore` the default. It begins with the starting source, then gives each
  research topic a horizontal branch with its claims, open questions, and next
  action.
- Keep a narrow right-hand source shelf on desktop so collected articles and
  documents remain visible while a branch is inspected.
- On narrow viewports, recompose into one ordered trail: source, branch, gaps,
  sources, action. Do not compress the desktop rails into tiny columns.
- Use asymmetry and rules rather than repeated floating cards. A branch earns a
  boundary because it is actionable, not because every object needs a container.

### Typography

- Display text names the live question or outcome, not the engine stage.
- Body text uses the existing system sans at readable measures.
- Small labels distinguish `Starting source`, `Open question`, `Collected
  source`, and `Possible output` without exposing internal schema names.
- Monospace is reserved for claim/evidence identifiers and timestamps.

### Color logic

- Cool near-white remains the dominant field; white belongs to documents and
  inspectable source objects.
- Indigo marks the active branch and primary action.
- Green, amber, and red retain their evidence meanings, but never dominate the
  entire page.
- A muted coral marks open questions because they are invitations to continue,
  not system failures.

### Material language

- Branch lines, editorial annotations, article rows, source locators, underlined
  questions, and a persistent working brief.
- One-pixel rules organize the workspace. Radius and shadow are limited to
  things the user can open, select, or submit.
- Motion only reveals a view, expands a branch, or opens the guided-output
  composer. Reduced motion removes these transitions.

### Forbidden defaults

- A graph of anonymous nodes.
- A dashboard headed by counts and status cards.
- A claim ledger as the primary product view.
- Equal `Brief / Research / Script` feature cards.
- A script button that silently writes without asking about angle, audience,
  format, length, evidence boundary, or desired takeaway.
- Supplemental sources hidden in a collapsed evidence appendix.

## Interaction architecture

### Explore

The user sees:

1. the source they started with;
2. research directions drawn from the case's planned topics;
3. claims and open questions attached to each direction;
4. supplemental articles, papers, and media already collected;
5. a `Research this branch` action;
6. a `Shape an output` action.

A gap is phrased as an idea to pursue. Verification status appears beside the
specific claim it affects, not as the title of the branch.

### Output

The finished brief, research report, or script remains readable in the center.
Its evidence appendix and full claim ledger are supporting disclosures. Existing
artifact versions and conversions remain the same case, not new projects.

### Sources

Collected sources are first-class objects with title, type, role, quality,
locator, and destination link. The source view distinguishes the starting source
from supplemental reporting and primary material.

### Guided script creation

`Shape an output` opens a form scoped to the selected branch. It asks for:

- output type;
- working angle or question;
- intended audience;
- target length;
- delivery format and tone;
- the conclusion the user wants tested, not automatically endorsed;
- whether unresolved gaps must block the draft or remain visible as caveats.

Submitting creates a topic-keyed artifact branch so two research directions do
not collapse into the same generic script. The branch retains its parent
artifact, selected topic, claims, evidence, constraints, and version history.

## Acceptance checks

- Within five seconds, the page reads as one source becoming several possible
  lines of inquiry.
- Research gaps look actionable rather than like a QA failure list.
- Supplemental sources are visible without opening the full fact-check appendix.
- A user can create two scripts from two topics and receive two separately keyed
  artifact branches.
- Script creation requires an explicit direction and exposes its audience,
  length, tone, and evidence-boundary controls.
- The output remains readable, exportable, and traceable.
- Desktop and mobile renders preserve the same source → branches → sources →
  output logic without overflow.

## Dashboard art-direction contract

### Design thesis

The dashboard is **an inbox for curiosity**. It should make starting from a
source feel immediate, then return the user to the research already in motion.
It is not a configuration wizard and it is not an account-usage report.

### Memory hook

**The source rail.** A pasted link or question crosses one deliberate line into
three possible jobs—understand, explore, or create—while the open trails below
show where earlier sources have already led.

### Composition

- Keep source capture above the fold, but collapse it into one calm work surface
  rather than three numbered panels.
- Put the source field first, the three plain-language intents directly beneath
  it, and advanced direction behind one optional disclosure.
- Make `Continue your trails` the dashboard's main body. A trail row names the
  research case, its starting source, latest usable output, and next action.
- Keep credits and API access as quiet workspace utilities, never as the page's
  visual counterweight.
- On mobile, preserve capture and recent-trail continuation. Hide desktop-only
  account detail so the page behaves like the product's capture companion, not
  a compressed research editor.

### Typography and color

- Use direct questions for display text and verbs for actions.
- Reserve monospace for compact metadata such as source type and update time.
- Indigo identifies the active intent and primary action. The cool neutral field
  remains dominant; status colors stay attached to evidence or progress only.

### Material language

- One bordered capture surface, editorial rules, source-type labels, and a
  continuing-work ledger.
- A trail earns a row because it has history and a next action. Avoid floating
  cards for navigation, plan limits, or every input option.
- Motion may confirm an intent choice or reveal optional direction; it must not
  delay capture.

### Forbidden defaults

- A giant numbered form that pushes its submit action below the first viewport.
- A narrow `Recent trails` sidebar that makes the user's work secondary.
- Raw owner IDs in the primary header.
- Equal feature cards for `Brief / Research / Script`.
- Credits, model settings, or API terminology as the dashboard's main story.

### Dashboard acceptance checks

- A new user can paste a source and find the submit action without scrolling on
  a common desktop viewport.
- A returning user can identify the latest case and open its newest artifact in
  one click.
- Existing research cases appear even when they were created outside a web job.
- Mobile shows the complete capture path before account or API utilities.
- The page still communicates that every output keeps its sources and open
  questions attached.
