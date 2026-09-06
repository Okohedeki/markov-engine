# First live editorial-discovery observations

Date: September 6, 2026. These are development observations, not a competitive
benchmark or a claim that generated material is ready to publish.

## Input and method

The only source input was the Stanford King Institute's
[assassination article](https://kinginstitute.stanford.edu/assassination-martin-luther-king-jr).
No labor, economic-politics, or preferred-story hint was supplied to the engine.
The first run extracted the source and claims. Subsequent runs reused those
records in fresh cases, preserving earlier results rather than overwriting them.

The local model endpoint was unavailable. The configured hybrid route used its
cloud fallback. Results are in the local, Git-ignored database
`data/editorial-bc4048ca503e.db`, cases 1 through 3.

## What actually happened

| Run | Inspected sources | Accepted leads | Observation |
| --- | ---: | ---: | --- |
| 1 | 3 | 0 | Joined words in search snippets caused relevant results to be filtered out; references were selected as passages. |
| 2 | 8 | 3 | Retrieval improved, but the leads clustered around assassination investigations. |
| 3 | 8 | 3 | Separate event, overlooked-context, and consequence questions produced a broader set. |

Run 3 generated these titles:

- The official reconstruction of the weapon's route.
- The labor fight that continued after the assassination.
- Federal response: troops in the streets and fair-housing legislation.

These are proposed angles, not independently fact-checked historical conclusions.
The labor angle received a sourced-interpretation label; the other two remained
single-source leads. Several passages from one page still count as one source.
Distinct URLs alone do not establish independent reporting or corroboration.

## Remaining quality work

- Check each factual assertion against its supporting passage, not merely whether
  a quoted substring exists. Exact-quote validation is only a provenance check.
- Dates, totals, causal language, and claims of independent corroboration require
  particular scrutiny before script generation.
- Prefer original records when a secondary source identifies them; coverage of
  blocked sources and deep document navigation still need improvement.
- Compare outputs on other unsteered topics and formats before generalizing from
  this one example. No competing product was run in this session.
- Develop paid scripts from selected evidence packets, then add series continuity
  and creator-catalog repetition controls. Those are subsequent slices.

## Verification and scope

Direct smoke checks covered case isolation, duplicate question/lens rejection,
source exclusion, exact passage retention, citation validation, research bounds,
cached reuse, partial-result labeling, and research-artifact rendering. The
changed Python files passed syntax/lint checks. No test suite was added or run.
The live run used a separate database, not the website's customer data. Existing
script/talking-point and story-mode entitlement rules were not changed.
