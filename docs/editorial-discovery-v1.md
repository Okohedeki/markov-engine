# Editorial discovery: first delivery slice

Markov develops source-backed stories for creators across formats. A link is a
starting point, not an outline to paraphrase. Cross-format output, citations,
and model access are necessary capabilities, not demonstrated differentiation.

## First backend slice

After source extraction and claim research, run one bounded editorial pass:

1. Propose up to three distinct questions grounded in the seed and its claims.
2. Search beyond the seed, including a challenge question for each direction.
3. Read retrieved source passages; search snippets are discovery leads only.
4. Use findings to choose a second, bounded research round when needed.
5. Return angle briefs explaining the additional information, supporting and
   challenging evidence, uncertainty, and the next unresolved question.

Questions are hypotheses, not findings. Retrieved context does not automatically
verify a seed claim. A political position, institutional conflict, or sequence of
events does not by itself establish causation or motive. Distinguish statements
made by a source from facts independently established by multiple sources.

Every accepted angle must cite inspected material outside the seed. Fewer useful
angles, including none, are acceptable. Reformatting one story does not create
another story. Novelty is relative to the seed, not a claim of global uniqueness.

## Implementation boundaries

- Keep the existing single-process job capacity and owner-scoped cases.
- Reuse source extraction, evidence storage, cost accounting, and model routing.
- Bound queries, retrieved pages, model context, and wall-clock research time.
- Persist a case-scoped audit result so completed discovery is not rerun during
  conversion. Do not mutate prior completed cases or customer data in development.
- Expose the result in the research artifact before changing the dashboard.
- Keep full scripts/talking points and serial story development behind paid
  access. This slice supplies angle briefs, not a free script or series.
- Do not add services, a graph database, model training, or a test framework.

## Following slices, not claims of completion

Develop a selected angle into a paid script using its evidence packet. Develop
series around distinct episode questions, new evidence per installment, and
continuity with previously approved work. Compare proposed stories with the
creator's own catalog before measuring broader audience novelty.

## Run without the GUI

From the repository root, with the existing model/search settings configured:

```powershell
python scripts/discover_stories.py "https://example.com/source"
```

This creates a separate `data/editorial-<id>.db` file and prints angle briefs,
source locators, search history, and completion status as JSON. Full inspected
passages and model-cost records stay in that database. No preferred angle is
supplied. The command runs extraction plus editorial discovery, not the older
claim-by-claim verification pipeline. Normal research jobs run both passes and
include the new angle sections in their existing research artifacts.

The discovery pass allows at most two rounds, eight inspected sources, twelve
page-read attempts, 180 seconds of research, and 60 seconds of final synthesis.
Source extraction precedes that budget. Offline mode returns no fabricated
angles. Exact-quote checks validate provenance, not the truth of an inference;
single-source leads remain visibly labeled and require editorial review.

## Manual quality comparison

Use identical, unsteered links in Markov and the closest competing workflows:
YouMind, Poppy, and Sourcebase/Foundry. No product superiority has been measured.
Compare usable distinct angles, information added beyond the seed, citation
accuracy, unsupported leaps, creator editing time, and cost per accepted story.
Keep live observations separate from deterministic smoke checks and mocks.
