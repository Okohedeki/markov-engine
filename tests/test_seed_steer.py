"""Following a key point steers discovery: its queries are generated and take
priority so the walk branches toward that point."""

from __future__ import annotations

from markov_engine import growth


def test_seed_queries_lead_with_the_point():
    qs = growth._seed_queries("James Earl Ray's escape route", "MLK assassination")
    texts = [q["q"] for q in qs]
    # The point itself leads, all at hop 0 (this is the chosen direction).
    assert texts[0] == "James Earl Ray's escape route"
    assert all(q["hop"] == 0 for q in qs)
    # Blends the chain subject in to keep it on-thread.
    assert any("MLK assassination" in t for t in texts)


def test_seed_queries_skip_redundant_subject():
    # When the seed already contains the subject, don't append a duplicate combo.
    qs = growth._seed_queries("MLK assassination new evidence", "MLK assassination")
    combos = [q["q"] for q in qs if q["q"].startswith("MLK assassination MLK")]
    assert combos == []
