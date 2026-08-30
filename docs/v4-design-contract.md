# Markov V4 design contract

## Product and conversion brief

- **Problem:** Professional publishers need to decide what is worth adding to a crowded information landscape; search, competitor research, and AI answers mostly expose what is already known.
- **Primary outcome:** A content lead can bring Markov a source, question, trend, or existing brief and quickly see the underdeveloped angle worth developing.
- **Best fit:** Lean company content teams first; research-led creators and editorial agencies second.
- **Poor fit:** People seeking a read-later archive, a personal knowledge base, a fact-checking product, or one-click finished copy.
- **Value proposition:** Markov compares current search results, AI answers, competitor coverage, previous work, and audience context to reveal useful missing connections—then structures the development and distribution plan while the user writes the final piece.
- **Primary CTA:** `Find my next idea`.
- **Proof:** The real Japan source packet and working product. No invented users, logos, quotes, or originality metrics.
- **Brand role:** Sage with a Creator accent: clear and commercially useful, rigorous without presenting as an academic truth engine.

## Direction brief

1. **Design thesis:** Markov feels like an energetic editorial command board where warm material becomes distinct signal, connection, opportunity, and audience fields—not nine variations of a beige magazine spread.
2. **Memory hook:** A familiar answer field visibly breaks open into an indigo missing connection, which becomes a pale-indigo idea and meets a teal audience signal.
3. **Content plan:** hero with AEO comparison and live example → existing answers versus missing opportunity → audience fit → source-to-idea workflow → idea-to-campaign workflow → authorship/AEO boundary → product proof and CTA.
4. **Interaction thesis:** comparison tabs reveal different information landscapes; campaign tabs show channel-native contribution; application feedback makes opportunity state and user judgment visible.
5. **Constraints:** FastAPI/Jinja; hosted SaaS positioning; no claims of exhaustive comparison; no finished prose by default; no fabricated proof; keyboard, touch, reduced motion, mobile reflow, and one-H1 discipline.

## Art-direction contract

1. **Composition:** Keep the hero asymmetric and demonstrative. Every later section gets a distinct silhouette: split comparison, compact audience band, horizontal workflow, dark campaign stage, concise boundary, product canvas. Reduce the public page to roughly six or seven desktop folds.
2. **Typography:** Literary serif only for the hero and editorial theses. Hero 72–84px; major headings 44–52px; examples 28–36px; body 17–19px; labels and metadata never below 12px. Avoid repeating giant headlines after the first viewport.
3. **Semantic color:**
   - Warm bone `#F4F0E8` — ambient field.
   - Ink `#1C1C19` — structure and existing landscape.
   - Accessible vermilion `#C43F22` — signal and primary action.
   - Pale signal `#F7D8CF` — captured input.
   - Indigo `#3F46B5` — missing connection and insight.
   - Pale indigo `#E8E9F7` — idea opportunity surface.
   - Teal `#0F6B5B` — audience relevance and performance.
   - Pale teal `#DCEDE8` — audience surface.
   State is always named as well as colored.
4. **Material language:** Coverage columns, annotated gaps, clipped source strips, strong color fields, directional arrows, and channel treatments. Hairlines remain useful but do not define every section. Square geometry and restrained offset shadows continue.
5. **Motion:** 160–220ms named-property transitions for selection, reveal, and focus. No looping ornament. Reduced motion removes nonessential movement.
6. **Voice:** Commercially direct, concrete, and audience-aware. Prefer `what everyone already says`, `what audiences still need`, `what has not been connected`, `what you can uniquely contribute`, and `why now` over forensic research terminology.
7. **Forbidden defaults:** no monochrome beige procession, repeated oversized serif headlines, tiny archival labels, random accent colors, violet CTA, generic card mosaic, fake dashboards, gradients, glow, glass, exhaustive-search claims, or finished-writing promises.

## Surface decisions

- **Landing:** AEO and the comparison set appear in the hero. Product proof moves earlier. Repetitive `what Markov finds`, standalone AEO, and long authorship sections are consolidated or removed.
- **Application:** Vermilion identifies incoming signals and primary action; indigo identifies connections and idea opportunities; teal identifies audience relevance. Existing landscape remains neutral. Metadata is raised to a readable minimum.
- **Login:** One concise value reminder, one compact opportunity visual, and one visually primary access form. No oversized return headline or progression strip.
- **Pricing/API/sample:** Reuse the same semantic colors and type scale; retain only copy that supports hosted product, agent use, and inspectable idea development.

## Acceptance checks

- First viewport says what Markov compares, why ordinary search/AI answers are insufficient, what the user receives, and who writes the final piece.
- Public page has visibly different section rhythms and is materially shorter than V3.
- White text on the primary action meets WCAG AA at normal text size.
- Signal, missing connection, idea opportunity, and audience relevance have consistent semantic color roles in public and product UI.
- Login is task-first and compact.
- Primary routes render at 1440×900, 1024×768, and 390×844 with no horizontal overflow, console failures, clipped controls, broken deep links, or keyboard regressions.
