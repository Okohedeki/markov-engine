---
name: frontend-visual-qa
description: Review and refine an implemented web UI through rendered screenshots, responsive checks, interaction states, and anti-template critique. Use after building or changing a page, or when a screenshot, URL, or frontend PR needs visual review.
---

# Frontend Visual QA

Do not judge a UI only from source code. Render it, inspect it at realistic sizes, identify failures, revise, and render again.

## Required review loop

For meaningful UI changes:

1. Run the application or static page.
2. Capture or inspect at least one desktop and one mobile viewport.
3. Compare the result against the product job and art-direction contract.
4. Record the highest-impact problems.
5. Fix them.
6. Render again before declaring the work finished.

Use the project's browser test tooling when available. Playwright is preferred when already installed. Do not add a heavy testing dependency solely for one screenshot when a simpler browser workflow exists.

## Pass 1: Five-second comprehension

Look at the page without reading every sentence.

Answer:

- What is the primary action?
- What does the product accept?
- What does it produce?
- What should the eye see first, second, and third?
- Is the page recognizable as this product rather than a generic template?

If those answers are unclear, fix hierarchy before polishing details.

## Pass 2: Composition and responsive behavior

Inspect:

- Overall silhouette and section rhythm.
- Alignment and edge relationships.
- Density versus negative space.
- Repetition of cards, borders, pills, and containers.
- Whether the signature move remains coherent across breakpoints.
- Text wrapping, awkward widows, clipping, overflow, and cropped media.
- Whether mobile is recomposed rather than merely stacked.
- Whether the CTA remains visible and understandable.

Avoid the common failure where desktop looks designed and mobile looks like a collapsed component library.

## Pass 3: Craft and states

Inspect:

- Type scale, line length, line height, and weight contrast.
- Color roles and accessible contrast.
- Spacing consistency.
- Border, radius, icon, and shadow consistency.
- Image quality and cropping.
- Hover, focus, active, disabled, loading, empty, and error states.
- Motion timing and reduced-motion behavior.
- Keyboard reachability and visible focus.

Small inconsistencies accumulate into an untrustworthy interface.

## Anti-slop audit

Flag any of the following when they are not justified by product behavior:

- Hero copy plus fake dashboard split layout.
- Centered headline plus identical card row.
- Decorative gradient backgrounds.
- Sparkles or magic icons standing in for explanation.
- Repeated badge-and-icon patterns.
- Excessive rounded containers.
- Generic stock illustrations or abstract blobs.
- Fake data, fake evidence, fake social proof, or fake application state.
- A page built from familiar sections without a distinctive narrative.
- A “bold” aesthetic that is just another common anti-slop costume.

Do not merely list these problems. Replace them with a product-specific composition or interaction.

## Content QA

Check that:

- Headings say something specific.
- CTAs accurately describe their destination.
- Examples use representative content.
- Claims about capabilities are true.
- Labels use the user's language.
- Empty filler sections have been removed.

Visual quality cannot rescue vague or misleading content.

## Review output

When reporting the review, prioritize issues by user impact:

1. Comprehension and product identity.
2. Interaction and responsive failures.
3. Hierarchy and composition.
4. Craft details.

Use specific observations tied to visible regions. Avoid vague feedback such as “make it pop” or “improve spacing.”

## Completion criteria

A UI is not finished until:

- The primary job is clear at desktop and mobile sizes.
- No important text or control overflows.
- The interface has one memorable, product-specific quality.
- Real content and truthful states are used.
- Keyboard and reduced-motion behavior are acceptable.
- The second render is materially better than the first.
