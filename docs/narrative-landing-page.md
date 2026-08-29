# Narrative landing-page comparison

Status: implementation contract, 2026-08-29

This page is a second public landing-page direction. It lives beside the current
homepage so the two approaches can be compared without changing `/`.

## Positioning brief

- **Product:** Markov is a web research and creation workspace, with an API for
  agents, that turns an encountered source into a continuing, evidence-linked
  Chain and finished work.
- **Best-fit visitor:** A creator, researcher, publisher, or curious operator who
  already has a video, article, paper, podcast, post, or question and needs a
  defensible angle or useful output rather than another summary.
- **Poor-fit visitor:** Someone whose main job is passive bookmarking, flashcard
  review, or building a general-purpose personal knowledge archive.
- **Outcome:** Move from “this is interesting” to an original brief, report,
  script, or newsletter whose sources, disagreements, and open questions remain
  inspectable.
- **Offer:** Open the working Markov workspace. The Japan Chain is the truthful,
  lower-commitment product proof.
- **Proof:** The real five-source Japan example, its mechanism, competing paths,
  evidence states, and three finished transformations. No customer counts,
  testimonials, logos, or unsupported performance claims are used.
- **Primary conversion:** `Start with a source` opens the existing workspace
  login. `See the Japan Chain` is the single lower-commitment secondary action.

Plain-language value proposition:

> Markov helps people who publish, explain, and investigate turn what they find
> into defensible original work without losing the evidence or unresolved
> questions along the way.

## Progress being sold

- **Functional:** One saved source becomes understanding, verification,
  connected research directions, and a finished artifact.
- **Emotional:** Replace the unease of repeating someone else's conclusion with
  confidence that the important mechanism and uncertainty were inspected.
- **Social:** Publish an angle that is original and can withstand scrutiny.
- **Dream:** Every encounter compounds into a private body of research that can
  keep producing better work instead of becoming another forgotten bookmark.
- **Triggering moment:** “I found something interesting. What is actually true,
  where does it lead, and what can I make from it?”

## Brand behavior

- **Primary archetype:** Sage — calm, clear, rigorous, and transparent about
  what is established or unresolved.
- **Secondary accent:** Creator — the research visibly develops into work rather
  than ending at organization or recall.
- **Voice:** exact, curious, constructive. Use short declarative turns followed
  by concrete mechanisms. Avoid omniscient claims, generic AI language, and
  pressure-heavy CTA copy.
- **Proof style:** show the source, intermediary reasoning, competing path, and
  output together; never ask a decorative graph to imply rigor.

## Reference principles

- **Recall:** Borrow its use of many recognizable source formats and legible
  product scenes, but reject its Save → Organize → Remember narrative. Markov's
  visual sequence must end in a chosen, defensible original idea.
- **The Pudding:** Each scroll step must create one explicit visual state and one
  editorial takeaway. The mobile version is deliberately shorter and stacked
  instead of inheriting a fragile desktop sticky composition.
- **MDN Intersection Observer guidance:** Use asynchronous entry thresholds for
  scene changes. Avoid a collection of independent scroll handlers; reserve one
  requestAnimationFrame-managed progress calculation for the opening convergence.

## Art-direction contract

### Design thesis

The page should feel like an argument assembling itself: familiar sources enter
as fragments, a single evidence line persists through understanding and
comparison, and the chosen direction tightens into finished work.

### Memory hook

**The unbroken thread.** A cobalt line begins at the captured source, branches
only when the evidence warrants it, and remains attached to the final document
and the source that returns three weeks later.

### Composition

- Desktop uses one opening encounter followed by four high-value product scenes,
  not an endless succession of animated feature blocks.
- The main demonstration is a two-column sticky stage: concise narrative steps
  advance beside one persistent working surface.
- The Japan source packet supplies all visible content. Source cards are HTML,
  not screenshot confetti, and labels remain readable at rest.
- The finish scene becomes document-shaped and visually quieter so the output,
  evidence margin, and open question dominate.
- Mobile abandons sticky scrub behavior. Each state becomes a complete stacked
  scene with its own artifact and no content hidden behind animation.

### Typography

- Display type makes one large, direct promise; it does not imitate editorial
  fashion for its own sake.
- Body copy stays compact and conversational. Labels are uppercase only when
  they describe a source type, connection role, or evidence state.
- A restrained monospace is used for timestamps, source types, and path labels.

### Color logic

- Warm near-white is the dominant field and document white marks completed work.
- Near-black holds the argument. Cobalt marks the continuous Markov thread and
  the selected action.
- Green means independent support, ochre marks context or interpretation, and
  coral marks an unresolved question. These colors stay local to the claim they
  qualify.

### Material language

- Source strips, transcript fragments, paper previews, evidence annotations,
  branching rules, document margins, and one persistent path line.
- Borders belong to inspectable sources and documents. Shadows are reserved for
  objects in motion so depth communicates arrival or selection.
- Motion shows causality: sources converge, context unfolds, evidence joins,
  branches compete, one path becomes a document, and a later source reconnects.

### Forbidden defaults

- Recreating Recall's card cloud, section order, copy, or knowledge-base promise.
- A generic node graph or “second brain” metaphor.
- A hero beside a fake dashboard screenshot.
- Scroll hijacking, blanket blur, overlapping sections, or motion that obscures
  the next sentence.
- Equal feature-card grids, decorative gradients, fabricated proof, and vague
  “AI-powered” language.

## Narrative states

1. **Encounter:** YouTube, TikTok, article, paper, podcast, and question converge
   around one real capture control.
2. **Understand:** The Japan thesis separates into substance, missing context,
   important claim, and open question.
3. **Verify and connect:** Reuters, NBER, Treasury, and Bank of Japan sources join
   with explicit connection roles.
4. **Follow the idea:** The strongest evidence, most original angle, and most
   consequential path remain visible while one is selected.
5. **Finish:** Brief, research report, script, and newsletter controls transform
   the selected path into a readable document with evidence and caveats attached.
6. **Return later:** A phone-captured source reconnects to the same Chain instead
   of creating a new isolated summary.

## Acceptance checks

- The existing `/` homepage remains unchanged and the comparison has its own URL.
- In five seconds the visitor can name the accepted sources, the transformation,
  the finished result, and the primary action.
- The page is recognizably Markov with the wordmark removed: the source is the
  first node, connection roles are typed, branches stay comparable, and the
  output retains evidence.
- Every demo state uses the real Japan example or clearly labeled interface copy.
- Keyboard users can activate source and output controls; focus is visible.
- Reduced motion and mobile receive complete static states, not missing content.
- Desktop and mobile have no horizontal overflow, hidden CTA, or overlapping
  sticky scenes.
