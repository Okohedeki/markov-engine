# Markov V3 redesign contract

## Product and outcome

- **Mode:** full redesign of the public website and authenticated product.
- **Surfaces:** conversion-focused marketing, onboarding, and an AI-assisted editorial strategy workspace.
- **Maturity:** defined product direction moving through develop and deliver.
- **Success:** a publishing professional understands Markov in five seconds, adds a signal, sees why an idea appears underdeveloped, and can develop it into a brief and channel plan without handing over authorship.

## Direction brief

1. **Problem:** People responsible for publishing original ideas need to find the valuable angle that existing coverage has missed because AI-generated copy and generic trend tools reproduce what already exists.
2. **Primary outcome:** Make `Find my next idea` the clearest action, then preserve context through Signal → Landscape → Opportunity → Development brief → Distribution plan.
3. **Visual thesis:** Markov feels like a contemporary editorial strategy desk—warm, rigorous, and actively annotated—with one vermilion thread carrying evidence into an idea.
4. **Content plan:** recognize the publishing problem → define the audience → show what Markov finds → prove one Japan transformation → show native channel treatments → explain authorship and AEO → show the real product → repeat the CTA.
5. **Interaction thesis:** the capture control reveals supported inputs without becoming a blank AI prompt; the Japan example exposes the missing connection step by step; product recommendations expand to show observation, interpretation, provenance, and rejection controls.
6. **Constraints:** FastAPI/Jinja and current backend behavior; no invented proof, exhaustive-search claims, or finished prose promises; semantic HTML; keyboard and touch access; reduced motion; desktop, tablet, and narrow mobile; no nested scroll regions.

## Positioning and conversion

- **Best fit:** lean company content teams, research-led creators, and editorial agencies professionally responsible for publishing distinctive ideas consistently.
- **Poor fit:** students, personal note-takers, read-later users, and people seeking one-click finished copy.
- **Value proposition:** Markov helps content teams and research-led creators find underdeveloped ideas for their audience without producing another version of what already exists or writing in their place.
- **Primary CTA:** `Find my next idea`.
- **Secondary CTA:** `See the Japan example` where a lower-commitment explanation is useful.
- **Proof inventory:** the existing Japan source packet and working product routes. No customer logos, testimonials, adoption metrics, or absolute originality claims are available and none will be implied.
- **Brand role:** Sage (rigorous, clear, candid) with a Creator accent (enabling, precise, generative). Avoid mystifying language, intellectual posturing, and claims of omniscience.

## Art-direction contract

1. **Design thesis:** A thoughtful editorial strategy desk, not project-management software: information is composed as briefs, annotations, and decision lines whose hierarchy mirrors editorial judgment.
2. **Memory hook:** A visible vermilion “idea thread” crosses the product—from an incoming signal, through the gap in existing coverage, to a developed opportunity—so the interface itself demonstrates Markov's job.
3. **Composition:** Asymmetric editorial grids; generous opening canvases; compact, high-information work areas; strong horizontal rules; deliberate alternation between full-width evidence and split decision views. Use containers only for interactive or stateful objects.
4. **Typography:** A literary system serif for public display and important theses; a neutral system sans for interface actions and explanation; small uppercase labels only where they orient rather than carry essential meaning; tabular numerals for scores and dates.
5. **Color logic:** Warm paper is the dominant field, near-black ink structures the page, muted stone supports secondary content, and vermilion marks the one primary action and the missing connection. Green, amber, and red remain semantic evidence states and never act alone without text.
6. **Material language:** Hairline rules, margin notes, editorial underlines, source slips, clipped annotations, and provenance trails. Shadows are reserved for dialogs or genuinely floating layers. Motion reveals continuity and state rather than decorating the page.
7. **Forbidden defaults:** no generic AI gradients, glow, glass, floating orbs, equal feature-card grids, fake dashboard chrome, unexplained single AI scores, tiny metadata chains, giant Markdown editor, finished-prose promises, nested scrolling, or fabricated proof.

## Responsive and state contract

- **Desktop:** persistent 248px workspace rail, flexible editorial canvas, optional context margin.
- **Tablet:** compact rail or top navigation, two-column work areas collapse deliberately, no horizontal clipping.
- **Mobile:** recomposed single-column flow with a bottom action dock for the current primary action; tables become labeled rows; touch targets remain at least 44px.
- **Motion:** 160–240ms state transitions on opacity, transform, color, and border; all nonessential movement removed under `prefers-reduced-motion`.
- **States:** capture includes idle, processing, validation error, and accepted feedback; recommendations expose supported, interpreted, disputed, and underexplored states; empty lists explain the next useful action; disabled controls explain what is missing.

## Acceptance checks

- Public hero communicates audience, comparison behavior, idea discovery, development/distribution, and authorship boundary in the first viewport.
- Application navigation uses Home, Signals, Ideas, Campaign Plans, Published, and Search.
- Opportunity ranking separates information gain from audience relevance.
- Generated recommendations show analyzed material, rationale, interpretation status, freshness, and user controls.
- Primary public and authenticated flows render cleanly at 1440×900, 1024×768, and 390×844, with keyboard focus, reduced motion, no horizontal overflow, and no console or resource failures.
