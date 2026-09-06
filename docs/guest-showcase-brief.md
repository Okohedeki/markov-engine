# Guest dashboard and walkthroughs

Extends the V11 soft-studio direction; does not introduce another visual system.

1. Problem: a frequent poster evaluating Markov needs to try the work before
   committing to an account, and see short demonstrations of the outcome.
2. Outcome: enter a guest dashboard, explore a discussion, collect angles, save
   a draft, and copy/export it without credentials.
3. Visual thesis: the same cool, softly dimensional writing studio, now organized
   as a practical workspace rather than a marketing example.
4. Content: compact guest disclosure → topics/angles → shortlist → saved drafts.
   Marketing adds a restrained walkthrough section, not another feature grid.
5. Interaction: real local persistence, independent draft formats, reversible
   shortlist changes, explicit reset confirmation, native video controls.
6. Constraints: existing FastAPI/Jinja, CSS tokens, browser storage and static
   export. Do not weaken account authentication or expose paid engine jobs.

Assumption pending user input: account-free use is a no-cost interactive guest
demo with labelled sample content, not live AI generation. All editing, saving,
navigation, copying and exporting genuinely work. Real AI guest usage requires
separate rate/spending limits. Keep the existing authenticated dashboard intact.

The memory hook remains one discussion becoming different things to post. DM
Sans, white writing surfaces, orange actions and restrained depth come from V11.
No invented metrics, simulated research/loading, auto-playing footage, fake
customer content or dead navigation. The Creator/Explorer voice stays precise,
curious and enabling. The primary evaluating CTA is “Try without an account”.

Create three short recordings of the implemented guest dashboard: find angles,
build a cross-topic shortlist, and edit/save/export a draft. Capture the actual
UI with browser recording; include poster images, timed captions and equivalent
text transcripts. Load video only on request; do not load third-party players.

Verification covers anonymous routes, auth preservation, mobile drawer/focus,
all guest views, saved draft formats, reload, empty and storage-error states,
export contents, reset confirmation, static hosting, video playback/captions,
and rendered desktop/tablet/mobile layouts.
