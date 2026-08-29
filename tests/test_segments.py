"""Structured extraction preserves stable source locators."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from markov_engine import extract
from markov_engine import transcribe as transcribe_module


FIXTURE = Path(__file__).parent / "fixtures" / "youtube_transcript.json"


def test_url_classification_uses_hostname_not_substring():
    assert extract.classify_url("https://youtube.com/watch?v=1") == "youtube"
    assert extract.classify_url("https://example.com/?next=youtube.com") == "article"
    assert extract.classify_url("https://notreddit.com/post") == "article"
    assert extract.classify_url("https://arxiv.org/pdf/1234.5678") == "pdf"


def test_json3_caption_segments_preserve_timestamps():
    payload = FIXTURE.read_text(encoding="utf-8")
    segments = extract._parse_json3_segments(payload, caption_source="youtube_manual")

    assert [segment.ordinal for segment in segments] == [0, 1, 2, 3]
    assert segments[1].text == "The first factual claim."
    assert segments[1].start_seconds == pytest.approx(2.2)
    assert segments[1].end_seconds == pytest.approx(5.3)
    assert segments[1].caption_source == "youtube_manual"
    assert segments[2].character_start > segments[1].character_end


def test_vtt_segments_preserve_cues():
    payload = """WEBVTT

00:00:01.000 --> 00:00:03.500
<c>First cue.</c>

00:03.500 --> 00:00:06.000
Second cue.
"""
    segments = extract._parse_timed_text_segments(
        payload, caption_source="youtube_auto"
    )
    assert [(s.text, s.start_seconds, s.end_seconds) for s in segments] == [
        ("First cue.", 1.0, 3.5),
        ("Second cue.", 3.5, 6.0),
    ]


def test_vtt_segments_collapse_rolling_youtube_windows():
    payload = """WEBVTT

00:00:01.000 --> 00:00:03.000
You are the best

00:00:03.000 --> 00:00:05.000
You are the best person for this

00:00:05.000 --> 00:00:07.000
person for this difficult job

00:00:07.000 --> 00:00:09.000
difficult job because you prepared

00:00:09.000 --> 00:00:11.000
because you prepared carefully yesterday

00:00:11.000 --> 00:00:13.000
carefully yesterday and checked everything.
"""
    segments = extract._parse_timed_text_segments(
        payload, caption_source="youtube_auto"
    )

    assert len(segments) == 1
    assert segments[0].text == (
        "You are the best person for this difficult job because you prepared "
        "carefully yesterday and checked everything."
    )
    assert segments[0].text.count("You are the best") == 1
    assert segments[0].start_seconds == pytest.approx(1)
    assert segments[0].end_seconds == pytest.approx(13)
    assert segments[0].caption_source == "youtube_auto"


@pytest.mark.asyncio
async def test_media_prefers_structured_captions(monkeypatch, tmp_path):
    caption_data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    async def fake_info(url):
        return {
            "title": "Fixture video",
            "description": "Description",
            "duration": 11,
            "subtitles": {"en": [{"ext": "json3", "data": caption_data}]},
        }

    async def fail_transcription(*args, **kwargs):
        raise AssertionError("captions should avoid transcription")

    monkeypatch.setattr(extract, "_ytdlp_extract_info", fake_info)
    monkeypatch.setattr(extract, "_download_and_transcribe_segments", fail_transcription)

    result = await extract._extract_media(
        "https://youtube.com/watch?v=fixture", "youtube", str(tmp_path), "base"
    )
    assert result.success is True
    assert len(result.segments) == 4
    assert result.segments[3].start_seconds == pytest.approx(8)
    assert "The first factual claim" in result.content_text


def test_article_segments_preserve_heading_path():
    payload = """
    <article>
      <h1>Report</h1><p>Opening paragraph.</p>
      <h2>Evidence</h2><p>The measured value was 42.</p>
      <h3>Limitations</h3><p>The sample was small.</p>
    </article>
    """
    segments = extract._article_segments_from_html(payload)
    assert [segment.section_title for segment in segments] == [
        "Report", "Evidence", "Limitations"
    ]
    assert segments[2].heading_path == ["Report", "Evidence", "Limitations"]


def test_pdf_segments_preserve_page_numbers(tmp_path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "fixture.pdf"
    document = fitz.open()
    page_one = document.new_page()
    page_one.insert_text((72, 72), "Page one evidence")
    page_two = document.new_page()
    page_two.insert_text((72, 72), "Page two qualification")
    document.save(path)
    document.close()

    _title, text, segments = extract._pymupdf_extract_structured_sync(str(path))
    assert "Page one evidence" in text
    assert [segment.page_number for segment in segments] == [1, 2]


@pytest.mark.asyncio
async def test_whisper_cache_is_keyed_by_model(monkeypatch):
    loaded = []

    def fake_load(model_size):
        loaded.append(model_size)
        return object()

    transcribe_module._models.clear()
    monkeypatch.setattr(transcribe_module, "_get_model_sync", fake_load)
    base = await transcribe_module._ensure_model("base")
    large = await transcribe_module._ensure_model("large-v3")
    base_again = await transcribe_module._ensure_model("base")

    assert base is base_again
    assert base is not large
    assert loaded == ["base", "large-v3"]
