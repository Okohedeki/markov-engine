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

The product shell is **a decision desk for unfinished ideas**. Capture stays one
click away, but Home is organized around what Markov finished, what changed, and
what the user should decide next. It is not an intake wizard, an engine monitor,
or an account-usage report.

### Functional, emotional, social, and long-term progress

- **Functional:** Turn everything the user finds into knowledge they can
  continue and work they can publish.
- **Emotional:** Replace the anxiety of losing a source or missing the important
  angle with a visible, evidence-linked next move.
- **Social:** Help the user make original work that can withstand scrutiny.
- **Dream:** Every saved source compounds into a private body of connected
  research instead of disappearing into bookmarks and disconnected summaries.

### Memory hook

**The next-move ledger.** Every active Chain is summarized by what Markov found
and one verb-led decision: review, compare, investigate, or finish.

### Composition

- Home begins with a compact `Add anything` control, followed immediately by
  work in progress, decisions waiting, continuing Chains, and recent outputs.
- Use one full-width activity ledger instead of an oversized form or a grid of
  generic metric cards.
- The permanent shell is `Home`, `Inbox`, `Chains`, `Outputs`, and `Search`.
  `Research` is an action inside a Chain, not a navigation destination.
- A Chain preview names the thesis, source and connection counts, what Markov
  found, and the next decision. Internal IDs and engine vocabulary stay hidden.
- Mobile is capture, review, and redirect: add a source, see processing, read a
  result, choose a branch, and send deep work back to desktop.

### Typography and color

- Display text names the user's work or next decision; it never becomes an
  oversized decorative wall.
- Body copy remains compact and readable. Monospace is reserved for source type,
  time, and other genuinely scan-worthy metadata.
- Indigo marks the current action. Evidence colors appear only beside the claim
  or branch they qualify.

### Material language

- Activity rows, decision queues, branch rankings, source timelines, document
  outlines, and margin evidence.
- One-pixel rules organize the desk. A border indicates an inspectable object;
  it is not the default wrapper for every paragraph.
- Motion may reveal capture modes, processing stages, branch support, or editor
  context. Reduced motion removes the transition without removing the state.

### Plain-language state model

- `Claim from the source`, not `Opinion or inference`.
- `Independently supported`, not `Verified` without qualification.
- `Needs verification`, not `Unverifiable`.
- `Ready to explore`, not `Planned`.
- `Weak direction`, `Competing evidence`, and `Open question` remain attached to
  the relevant branch rather than becoming global warnings.

### Forbidden defaults

- A capture form that occupies the dashboard's entire first screen.
- Navigation links that only jump to sections of the same page.
- Credits, plan names, model settings, or API keys in the primary product story.
- Seven fully expanded branches with repeated claim ledgers and duplicate calls
  to action.
- A generated output presented as one unstructured wall of text.
- Fake Google/email authentication before a real identity provider exists.

### Dashboard acceptance checks

- A returning user sees current work and its next decision in the first viewport.
- Add-anything remains continuously accessible but visually subordinate to the
  work already in motion.
- Each shell destination has a real URL and a distinct, useful surface.
- Existing engine- and API-created cases appear even without a web job.
- Mobile exposes capture and the first decision queue without desktop utilities.
- The page explains the Markov lifecycle in user terms: reading, mapping claims,
  checking evidence, finding connections, and presenting directions.
