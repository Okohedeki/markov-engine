---
name: frontend-art-direction
description: Define a distinctive visual direction before building or redesigning a web UI. Use for landing pages, dashboards, application screens, component systems, visual refreshes, and UI critiques where a generic template would be unacceptable.
---

# Frontend Art Direction

Treat UI work as art direction first and component assembly second. The goal is not to make an interface look more decorated. The goal is to make the product's purpose visible in the composition, type, content, motion, and interaction.

## Before writing UI code

Inspect the existing product, copy, screenshots, brand assets, application states, and technical stack. Identify:

- The person using the interface and the moment that brought them there.
- The job they are trying to complete.
- The emotion the interface should create.
- The product behavior that is genuinely distinctive.
- The information that deserves visual dominance.
- The existing conventions worth preserving.

Do not jump directly from requirements to a hero, card grid, and CTA.

## Write an art-direction contract

Before implementation, state a compact direction containing:

1. **Design thesis** — one sentence describing how the interface should feel and why that fits the product.
2. **Memory hook** — the one visual or interactive idea a person should remember after closing the page.
3. **Composition** — density, rhythm, alignment, asymmetry, scale, and use of negative space.
4. **Typography** — the role of display, body, labels, and data text. Typography must support the product character, not merely look fashionable.
5. **Color logic** — dominant field, accent role, semantic colors, and contrast behavior.
6. **Material language** — imagery, texture, diagrams, documents, media, borders, shadows, or motion that belong to this product.
7. **Forbidden defaults** — the likely generic fallbacks that must not appear.

Every major visual choice must trace back to this contract.

## Use references as evidence, not templates

When browsing or reference material is available, study at least three relevant sources before choosing a direction:

- One direct or adjacent product.
- One non-software reference such as editorial design, maps, archives, field guides, industrial controls, packaging, film titles, museum systems, scientific publishing, or physical tools.
- One reference selected for interaction, information hierarchy, or motion rather than surface style.

For each reference, extract one principle. Do not copy an entire aesthetic or recreate a competitor layout.

If the direction is still ambiguous, create two or three small direction studies in one preview. Each study must vary the underlying composition and visual metaphor, not just colors or fonts. Choose the direction that best expresses the product job before building the full page.

## Reject generated defaults

These are warning signs, not a complete blacklist:

- Left-aligned marketing copy beside a fake dashboard.
- A centered headline followed by three equal feature cards.
- A six-card feature grid used because the page needs more content.
- Purple or blue gradients, glass panels, glows, sparkles, and floating blobs without product meaning.
- Excessive rounded rectangles, pills, badges, and icon bubbles.
- Fake customer logos, fabricated metrics, fictional quotes, or invented evidence.
- Generic copy such as “powerful,” “seamless,” “revolutionary,” or “supercharge.”
- Decorative charts and screenshots that do not demonstrate the core job.
- A dark terminal aesthetic used only to look technical.
- Beige editorial serif layouts used only to look tasteful.
- Brutalism, newspaper rules, grain, or monospace labels applied as an anti-slop costume.

Avoiding one cliché by switching to another is still slop.

## Build from real content

Use realistic product copy, true states, real source types, actual constraints, and representative outputs. Content is part of the visual system.

- Show the user's real task rather than an abstract feature claim.
- Prefer one complete transformation over many shallow feature cards.
- Let labels name actions and objects in the user's language.
- Do not invent social proof or product capabilities.
- If a demo cannot function, label it honestly and make it a useful example rather than a fake application.

## Spend boldness deliberately

Choose one primary place for expressive risk: composition, typography, interaction, imagery, motion, or material treatment. Keep the rest disciplined enough to support it.

A distinctive interface is not one where every element competes for attention. It is one where the memorable move is inseparable from the product.

## Production floor

A strong aesthetic direction never excuses poor usability.

- Support mobile, tablet, and desktop layouts.
- Preserve keyboard navigation and visible focus.
- Respect reduced-motion preferences.
- Maintain readable line lengths and sufficient contrast.
- Design hover, focus, active, disabled, loading, empty, and error states where applicable.
- Reuse the project's existing stack and conventions unless there is a concrete reason to change them.
- Prefer design tokens over scattered values.

## Final self-check

Before calling the design finished, answer:

- Could this page belong to five unrelated AI startups after swapping the logo?
- Does the first screen demonstrate the product's actual job?
- Is there one memorable quality that can be described without naming a color?
- Did the design use real content and truthful proof?
- Does every section earn its space?
- Did the implementation preserve the art-direction contract?

If the answer to the first question is yes, redesign it.
