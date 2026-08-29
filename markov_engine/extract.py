"""Content extraction from URLs and local files. PURE — no Store, no engine state.

Dispatches by URL/domain to the right extractor: PDFs (PyMuPDF), articles
(trafilatura), Twitter (fxtwitter API), Reddit (JSON API), and media
(yt-dlp + whisper transcription as a fallback when no captions exist).
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from markov_engine.transcribe import transcribe_segments

logger = logging.getLogger(__name__)

# Domains mapped to source types
_DOMAIN_MAP = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "reddit.com": "reddit",
    "open.spotify.com": "audio",
    "soundcloud.com": "audio",
    "podcasts.apple.com": "audio",
    "arxiv.org": "article",
    "scholar.google.com": "article",
    "pubmed.ncbi.nlm.nih.gov": "article",
    "doi.org": "article",
}

# Source types where we should attempt audio download + transcription
_MEDIA_TYPES = {"youtube", "tiktok", "instagram", "twitter", "reddit", "audio", "media"}


@dataclass
class ExtractedSegment:
    """One stable, source-addressable unit of extracted content."""

    ordinal: int
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    page_number: int | None = None
    section_title: str | None = None
    heading_path: list[str] = field(default_factory=list)
    character_start: int | None = None
    character_end: int | None = None
    speaker: str | None = None
    caption_source: str | None = None

    def as_dict(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "text": self.text,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "page_number": self.page_number,
            "section_title": self.section_title,
            "heading_path": self.heading_path,
            "character_start": self.character_start,
            "character_end": self.character_end,
            "speaker": self.speaker,
            "caption_source": self.caption_source,
        }


@dataclass
class ExtractedContent:
    url: str | None
    source_type: str
    title: str
    content_text: str
    metadata: dict = field(default_factory=dict)
    segments: list[ExtractedSegment] = field(default_factory=list)
    success: bool = True
    error: str | None = None


def classify_url(url: str) -> str:
    """Classify a URL into a source type based on domain."""
    url_lower = url.lower().rstrip("/")
    parsed = urlparse(url_lower)
    host = (parsed.hostname or "").lower()
    # Check if URL points to a PDF
    if url_lower.endswith(".pdf"):
        return "pdf"
    # arxiv.org/pdf/ URLs are always PDFs
    if (host == "arxiv.org" or host.endswith(".arxiv.org")) and parsed.path.startswith("/pdf/"):
        return "pdf"
    for domain, stype in _DOMAIN_MAP.items():
        if host == domain or host.endswith("." + domain):
            return stype
    return "article"


async def extract_content(
    url: str, tmp_dir: str, whisper_model: str | None = "base"
) -> ExtractedContent:
    """Extract content from a URL. Main entry point."""
    source_type = classify_url(url)

    if source_type == "pdf":
        return await _extract_pdf(url, tmp_dir)
    elif source_type == "twitter":
        return await _extract_twitter(url, tmp_dir, whisper_model)
    elif source_type == "reddit":
        return await _extract_reddit(url, tmp_dir, whisper_model)
    elif source_type in _MEDIA_TYPES:
        return await _extract_media(url, source_type, tmp_dir, whisper_model)
    else:
        return await _extract_article(url)


async def _extract_media(
    url: str, source_type: str, tmp_dir: str, whisper_model: str
) -> ExtractedContent:
    """Extract content from media URLs using yt-dlp + optional whisper transcription."""
    try:
        # Step 1: Get metadata and try to get subtitles
        info = await _ytdlp_extract_info(url)
        if info is None:
            # yt-dlp failed, try article extraction as fallback
            return await _extract_article(url)

        title = info.get("title", "")
        description = info.get("description", "")

        # Step 2: Try to get subtitles/captions
        caption_segments = await _extract_caption_segments(info)
        subtitle_text = " ".join(segment.text for segment in caption_segments)

        if subtitle_text:
            content = (
                f"{description}\n\n--- Transcript ---\n{subtitle_text}"
                if description
                else subtitle_text
            )
            return ExtractedContent(
                url=url,
                source_type=source_type,
                title=title,
                content_text=content,
                metadata=_extract_metadata(info),
                segments=caption_segments,
            )

        # Step 3: No subtitles — download audio and transcribe (skip when
        # transcription is disabled; metadata + description are enough).
        transcript_segments = (
            await _download_and_transcribe_segments(url, tmp_dir, whisper_model)
            if whisper_model
            else []
        )
        transcript = " ".join(segment.text for segment in transcript_segments)

        if transcript:
            content = (
                f"{description}\n\n--- Transcript ---\n{transcript}"
                if description
                else transcript
            )
        elif description:
            content = description
        else:
            content = title

        return ExtractedContent(
            url=url,
            source_type=source_type,
            title=title,
            content_text=content,
            metadata=_extract_metadata(info),
            segments=(
                transcript_segments
                or _plain_segments(description or title, section_title="Description")
            ),
        )

    except Exception as e:
        logger.exception("Media extraction failed for %s", url)
        # Fallback to article extraction
        try:
            return await _extract_article(url)
        except Exception:
            return ExtractedContent(
                url=url,
                source_type=source_type,
                title="",
                content_text="",
                success=False,
                error=str(e),
            )


async def _ytdlp_extract_info(url: str) -> dict | None:
    """Use yt-dlp to extract video/audio metadata without downloading."""
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _ytdlp_info_sync, url)
    except Exception as e:
        logger.warning("yt-dlp info extraction failed for %s: %s", url, e)
        return None


def _ytdlp_info_sync(url: str) -> dict | None:
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def _with_character_offsets(
    segments: list[ExtractedSegment], *, start_at: int = 0
) -> list[ExtractedSegment]:
    cursor = start_at
    for ordinal, segment in enumerate(segments):
        segment.ordinal = ordinal
        segment.character_start = cursor
        cursor += len(segment.text)
        segment.character_end = cursor
        cursor += 1
    return segments


def _plain_segments(
    text: str, *, section_title: str | None = None, caption_source: str | None = None
) -> list[ExtractedSegment]:
    clean = (text or "").strip()
    if not clean:
        return []
    return _with_character_offsets(
        [
            ExtractedSegment(
                ordinal=0,
                text=clean,
                section_title=section_title,
                caption_source=caption_source,
            )
        ]
    )


def segment_text(text: str, *, max_chars: int = 1600) -> list[ExtractedSegment]:
    """Split customer-provided text into stable, addressable source segments.

    Paragraph boundaries are preserved whenever possible. Oversized paragraphs
    are split on sentence boundaries, then on the configured character ceiling
    as a last resort. Character offsets always address the original trimmed
    input; segment text only normalizes internal whitespace for analysis.
    """
    if max_chars < 256:
        raise ValueError("max_chars must be at least 256")
    clean = (text or "").strip()
    if not clean:
        return []

    spans: list[tuple[int, int, str | None]] = []
    section_title: str | None = None
    paragraphs = list(
        re.finditer(r"\S(?:.*?\S)?(?=\r?\n[ \t]*\r?\n|\Z)", clean, re.DOTALL)
    )
    for paragraph in paragraphs:
        raw = paragraph.group(0)
        heading = re.fullmatch(r"[ \t]*#{1,6}[ \t]+(.+?)[ \t]*", raw)
        if heading:
            section_title = re.sub(r"\s+", " ", heading.group(1)).strip()
            continue
        start = paragraph.start()
        end = paragraph.end()
        if end - start <= max_chars:
            spans.append((start, end, section_title))
            continue

        sentence_matches = list(
            re.finditer(r"\S(?:.*?\S)?(?:[.!?](?=\s+|\Z)|\Z)", raw, re.DOTALL)
        )
        cursor = 0
        while cursor < len(sentence_matches):
            first = sentence_matches[cursor]
            chunk_start = first.start()
            chunk_end = first.end()
            cursor += 1
            while cursor < len(sentence_matches):
                candidate_end = sentence_matches[cursor].end()
                if candidate_end - chunk_start > max_chars:
                    break
                chunk_end = candidate_end
                cursor += 1
            if chunk_end - chunk_start <= max_chars:
                spans.append((start + chunk_start, start + chunk_end, section_title))
                continue
            # A single sentence can exceed the ceiling. Preserve exact offsets
            # while splitting it into bounded, whitespace-aligned slices.
            slice_start = chunk_start
            while slice_start < chunk_end:
                slice_end = min(slice_start + max_chars, chunk_end)
                if slice_end < chunk_end:
                    boundary = raw.rfind(" ", slice_start, slice_end)
                    if boundary > slice_start:
                        slice_end = boundary
                spans.append((start + slice_start, start + slice_end, section_title))
                slice_start = slice_end
                while slice_start < chunk_end and raw[slice_start].isspace():
                    slice_start += 1

    return [
        ExtractedSegment(
            ordinal=ordinal,
            text=re.sub(r"\s+", " ", clean[start:end]).strip(),
            section_title=title,
            character_start=start,
            character_end=end,
        )
        for ordinal, (start, end, title) in enumerate(spans)
        if clean[start:end].strip()
    ]


def _parse_json3_segments(
    payload: str | dict, *, caption_source: str
) -> list[ExtractedSegment]:
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except (TypeError, ValueError):
        return []
    output: list[ExtractedSegment] = []
    for event in data.get("events", []) if isinstance(data, dict) else []:
        pieces = event.get("segs") or []
        text = "".join(str(piece.get("utf8") or "") for piece in pieces)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        start = float(event.get("tStartMs") or 0) / 1000
        duration = float(event.get("dDurationMs") or 0) / 1000
        output.append(
            ExtractedSegment(
                ordinal=len(output),
                text=text,
                start_seconds=start,
                end_seconds=start + duration,
                caption_source=caption_source,
            )
        )
    return _with_character_offsets(output)


def _caption_timestamp(raw: str) -> float | None:
    value = raw.strip().replace(",", ".")
    try:
        parts = [float(part) for part in value.split(":")]
    except ValueError:
        return None
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return None


def _parse_timed_text_segments(
    payload: str, *, caption_source: str
) -> list[ExtractedSegment]:
    """Parse WebVTT or SRT cues without discarding cue boundaries."""
    lines = payload.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[ExtractedSegment] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if "-->" not in line:
            index += 1
            continue
        left, right = line.split("-->", 1)
        start = _caption_timestamp(left)
        end = _caption_timestamp(right.strip().split(" ", 1)[0])
        index += 1
        cue_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            cue_lines.append(lines[index].strip())
            index += 1
        text = html.unescape(re.sub(r"<[^>]+>", "", " ".join(cue_lines)))
        text = re.sub(r"\s+", " ", text).strip()
        if text and start is not None and end is not None:
            # Auto-captions often repeat the previous rolling window. Remove exact
            # consecutive duplicates while keeping stable timestamps.
            if output and output[-1].text == text:
                output[-1].end_seconds = max(output[-1].end_seconds or 0, end)
            else:
                output.append(
                    ExtractedSegment(
                        ordinal=len(output),
                        text=text,
                        start_seconds=start,
                        end_seconds=end,
                        caption_source=caption_source,
                    )
                )
        index += 1
    return _with_character_offsets(_collapse_rolling_captions(output))


def _caption_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _caption_overlap(left: str, right: str) -> int:
    """Return the largest word overlap between a prior cue and a new cue."""
    left_words = _caption_words(left)
    right_words = _caption_words(right)
    for size in range(min(len(left_words), len(right_words), 80), 0, -1):
        if left_words[-size:] == right_words[:size]:
            return size
    return 0


def _caption_delta(text: str, overlap_words: int) -> str:
    """Remove a normalized-word prefix without losing the cue's punctuation."""
    if overlap_words <= 0:
        return text.strip()
    raw_words = text.split()
    consumed = 0
    for index, raw_word in enumerate(raw_words):
        consumed += len(_caption_words(raw_word))
        if consumed >= overlap_words:
            return " ".join(raw_words[index + 1 :]).strip()
    return ""


def _collapse_rolling_captions(
    segments: list[ExtractedSegment],
    *,
    window_seconds: float = 20,
    max_chars: int = 600,
) -> list[ExtractedSegment]:
    """Collapse YouTube's rolling VTT windows into useful timestamped passages.

    Ordinary VTT/SRT cue files remain untouched. Rolling captions are detected
    only when repeated word windows occur throughout the track. The resulting
    passages retain bounded start/end timestamps without feeding dozens of
    near-duplicate cues into claim extraction.
    """
    if len(segments) < 3:
        return segments
    overlap_pairs = sum(
        _caption_overlap(left.text, right.text) >= 3
        for left, right in zip(segments, segments[1:])
    )
    if overlap_pairs / max(1, len(segments) - 1) < 0.2:
        return segments

    emitted_normalized: list[str] = []
    compacted: list[ExtractedSegment] = []
    for cue in segments:
        normalized = _caption_words(cue.text)
        overlap = 0
        for size in range(min(len(emitted_normalized), len(normalized), 80), 0, -1):
            if emitted_normalized[-size:] == normalized[:size]:
                overlap = size
                break
        if overlap >= len(normalized):
            continue
        delta = _caption_delta(cue.text, overlap)
        if not delta:
            continue
        emitted_normalized.extend(_caption_words(delta))
        active = compacted[-1] if compacted else None
        within_window = (
            active is not None
            and active.start_seconds is not None
            and cue.end_seconds is not None
            and cue.end_seconds - active.start_seconds <= window_seconds
        )
        if active is not None and within_window and len(active.text) + len(delta) + 1 <= max_chars:
            active.text = f"{active.text} {delta}".strip()
            active.end_seconds = cue.end_seconds
        else:
            compacted.append(
                ExtractedSegment(
                    ordinal=len(compacted),
                    text=delta,
                    start_seconds=cue.start_seconds,
                    end_seconds=cue.end_seconds,
                    caption_source=cue.caption_source,
                )
            )
    return compacted or segments


def _subtitle_payload_segments(
    payload, *, extension: str, caption_source: str
) -> list[ExtractedSegment]:
    if extension == "json3" or isinstance(payload, dict):
        return _parse_json3_segments(payload, caption_source=caption_source)
    if isinstance(payload, str):
        return _parse_timed_text_segments(payload, caption_source=caption_source)
    return []


async def _extract_caption_segments(info: dict) -> list[ExtractedSegment]:
    """Fetch and parse the best available English caption track from yt-dlp."""
    sources = (
        ("requested_subtitles", "youtube_caption"),
        ("subtitles", "youtube_manual"),
        ("automatic_captions", "youtube_auto"),
    )
    for sub_key, caption_source in sources:
        subs = info.get(sub_key) or {}
        for lang in ("en", "en-US", "en-GB"):
            sub_data = subs.get(lang) if isinstance(subs, dict) else None
            if not sub_data:
                continue
            formats = sub_data if isinstance(sub_data, list) else [sub_data]
            formats = sorted(
                (fmt for fmt in formats if isinstance(fmt, dict)),
                key=lambda fmt: {"json3": 0, "vtt": 1, "srt": 2}.get(
                    str(fmt.get("ext") or "").lower(), 9
                ),
            )
            for fmt in formats:
                extension = str(fmt.get("ext") or "vtt").lower()
                if "data" in fmt:
                    segments = _subtitle_payload_segments(
                        fmt["data"],
                        extension=extension,
                        caption_source=caption_source,
                    )
                    if segments:
                        return segments
                file_path = fmt.get("filepath") or fmt.get("filename")
                if file_path and os.path.isfile(file_path):
                    try:
                        with open(file_path, encoding="utf-8") as handle:
                            payload = handle.read()
                    except OSError:
                        payload = ""
                    segments = _subtitle_payload_segments(
                        payload,
                        extension=extension,
                        caption_source=caption_source,
                    )
                    if segments:
                        return segments
                subtitle_url = fmt.get("url")
                if subtitle_url:
                    try:
                        async with httpx.AsyncClient(
                            follow_redirects=True, timeout=30
                        ) as client:
                            response = await client.get(
                                subtitle_url, headers={"User-Agent": "Mozilla/5.0"}
                            )
                            response.raise_for_status()
                        segments = _subtitle_payload_segments(
                            response.text,
                            extension=extension,
                            caption_source=caption_source,
                        )
                        if segments:
                            return segments
                    except Exception as exc:
                        logger.debug("Caption fetch failed for %s: %s", subtitle_url, exc)
    return []


def _extract_subtitles_from_info(info: dict) -> str | None:
    """Compatibility helper for inline caption data.

    Network-backed caption URLs require the async ``_extract_caption_segments``
    path used by media extraction.
    """
    for sub_key, caption_source in (
        ("requested_subtitles", "youtube_caption"),
        ("subtitles", "youtube_manual"),
        ("automatic_captions", "youtube_auto"),
    ):
        subs = info.get(sub_key) or {}
        for lang in ("en", "en-US", "en-GB"):
            sub_data = subs.get(lang) if isinstance(subs, dict) else None
            formats = sub_data if isinstance(sub_data, list) else [sub_data]
            for fmt in formats:
                if not isinstance(fmt, dict) or "data" not in fmt:
                    continue
                segments = _subtitle_payload_segments(
                    fmt["data"],
                    extension=str(fmt.get("ext") or "vtt").lower(),
                    caption_source=caption_source,
                )
                if segments:
                    return " ".join(segment.text for segment in segments)
    return None


def _extract_metadata(info: dict) -> dict:
    """Pull useful metadata from yt-dlp info."""
    keys = [
        "uploader", "upload_date", "duration", "view_count",
        "like_count", "channel", "webpage_url", "thumbnail",
    ]
    return {k: info[k] for k in keys if k in info and info[k] is not None}


async def _download_and_transcribe(
    url: str, tmp_dir: str, whisper_model: str
) -> str | None:
    """Download audio from URL via yt-dlp and transcribe with whisper.

    A falsy ``whisper_model`` disables transcription entirely (metadata-only
    ingestion) — much faster for video/social discovery.
    """
    segments = await _download_and_transcribe_segments(url, tmp_dir, whisper_model)
    return " ".join(segment.text for segment in segments)


async def _download_and_transcribe_segments(
    url: str, tmp_dir: str, whisper_model: str
) -> list[ExtractedSegment]:
    """Download audio and preserve every Whisper segment boundary."""
    if not whisper_model:
        return []
    os.makedirs(tmp_dir, exist_ok=True)
    import tempfile

    handle, audio_path = tempfile.mkstemp(prefix="markov_audio_", dir=tmp_dir)
    os.close(handle)
    try:
        os.remove(audio_path)
    except OSError:
        pass

    try:
        loop = asyncio.get_running_loop()
        actual_path = await loop.run_in_executor(
            None, _ytdlp_download_audio_sync, url, audio_path
        )
        if actual_path and os.path.exists(actual_path):
            transcript = await transcribe_segments(
                actual_path, model_size=whisper_model
            )
            return _with_character_offsets(
                [
                    ExtractedSegment(
                        ordinal=index,
                        text=segment.text,
                        start_seconds=segment.start_seconds,
                        end_seconds=segment.end_seconds,
                        speaker=segment.speaker,
                        caption_source=f"whisper:{whisper_model}",
                    )
                    for index, segment in enumerate(transcript)
                ]
            )
        return []
    except Exception as e:
        logger.warning("Download+transcribe failed for %s: %s", url, e)
        return []
    finally:
        for ext in ("", ".opus", ".m4a", ".webm", ".mp3", ".wav", ".ogg"):
            p = audio_path + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _ytdlp_download_audio_sync(url: str, output_path: str) -> str | None:
    """Download audio-only via yt-dlp. Returns path to downloaded file."""
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": output_path + ".%(ext)s",
        "max_filesize": 100 * 1024 * 1024,  # 100MB limit
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info:
            ext = info.get("ext", "opus")
            return f"{output_path}.{ext}"
    return None


async def _extract_twitter(
    url: str, tmp_dir: str, whisper_model: str
) -> ExtractedContent:
    """Extract tweet content using the fxtwitter API, with yt-dlp fallback for video."""
    import re

    match = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/(\d+)", url)
    if not match:
        return await _extract_media(url, "twitter", tmp_dir, whisper_model)

    username, tweet_id = match.group(1), match.group(2)
    api_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            # fxtwitter 403s requests without a browser-like User-Agent.
            resp = await client.get(api_url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()

        tweet = data.get("tweet", {})
        author_name = tweet.get("author", {}).get("name", username)
        author_handle = tweet.get("author", {}).get("screen_name", username)
        text = tweet.get("text", "")
        created = tweet.get("created_at", "")

        parts = [f"@{author_handle} ({author_name})"]
        if created:
            parts.append(f"Posted: {created}")
        parts.append("")
        parts.append(text)

        quote = tweet.get("quote")
        if quote:
            qt_author = quote.get("author", {}).get("screen_name", "")
            qt_text = quote.get("text", "")
            parts.append(f"\n--- Quoted @{qt_author} ---\n{qt_text}")

        media = tweet.get("media", {})
        videos = media.get("videos") or []
        if videos or media.get("video"):
            transcript = await _download_and_transcribe(url, tmp_dir, whisper_model)
            if transcript:
                parts.append(f"\n--- Video Transcript ---\n{transcript}")

        title = f"@{author_handle}: {text[:80]}{'...' if len(text) > 80 else ''}"

        content_text = "\n".join(parts)
        return ExtractedContent(
            url=url,
            source_type="twitter",
            title=title,
            content_text=content_text,
            metadata={
                "author": author_handle,
                "likes": tweet.get("likes", 0),
                "retweets": tweet.get("retweets", 0),
                "replies": tweet.get("replies", 0),
            },
            segments=_plain_segments(content_text, section_title="Post"),
        )

    except Exception as e:
        logger.warning("fxtwitter extraction failed for %s: %s, trying yt-dlp", url, e)
        return await _extract_media(url, "twitter", tmp_dir, whisper_model)


async def _extract_reddit(
    url: str, tmp_dir: str, whisper_model: str
) -> ExtractedContent:
    """Extract Reddit post content using Reddit's JSON API, with yt-dlp fallback for video."""
    import re

    clean_url = re.split(r"[?#]", url)[0].rstrip("/") + "/"

    json_url = (
        clean_url.replace("www.reddit.com", "old.reddit.com").replace(
            "://reddit.com", "://old.reddit.com"
        )
        + ".json"
    )

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(json_url, headers={"User-Agent": "markov/0.1"})
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, list) or len(data) < 1:
            return await _extract_media(url, "reddit", tmp_dir, whisper_model)

        post_data = data[0]["data"]["children"][0]["data"]
        title = post_data.get("title", "")
        selftext = post_data.get("selftext", "")
        author = post_data.get("author", "")
        subreddit = post_data.get("subreddit_name_prefixed", "")
        score = post_data.get("score", 0)

        parts = [f"{subreddit} - u/{author}"]
        parts.append(f"Score: {score}")
        parts.append(f"\n{title}")

        if selftext:
            parts.append(f"\n{selftext}")

        if not post_data.get("is_self") and post_data.get("url_overridden_by_dest"):
            parts.append(f"\nLinked: {post_data['url_overridden_by_dest']}")

        is_video = post_data.get("is_video", False)
        if is_video:
            transcript = await _download_and_transcribe(url, tmp_dir, whisper_model)
            if transcript:
                parts.append(f"\n--- Video Transcript ---\n{transcript}")

        if len(data) > 1:
            comments = data[1]["data"]["children"]
            top_comments = []
            for c in comments[:5]:
                if c["kind"] != "t1":
                    continue
                cdata = c["data"]
                cbody = cdata.get("body", "")
                cauthor = cdata.get("author", "")
                cscore = cdata.get("score", 0)
                if cbody:
                    top_comments.append(f"u/{cauthor} ({cscore} pts): {cbody[:500]}")

            if top_comments:
                parts.append("\n--- Top Comments ---")
                parts.extend(top_comments)

        content_text = "\n".join(parts)
        return ExtractedContent(
            url=url,
            source_type="reddit",
            title=title,
            content_text=content_text,
            metadata={"author": author, "subreddit": subreddit, "score": score},
            segments=_plain_segments(content_text, section_title="Post and comments"),
        )

    except Exception as e:
        logger.warning("Reddit JSON extraction failed for %s: %s, trying yt-dlp", url, e)
        return await _extract_media(url, "reddit", tmp_dir, whisper_model)


async def _extract_pdf(url: str, tmp_dir: str) -> ExtractedContent:
    """Download a PDF and extract text from it using PyMuPDF."""
    os.makedirs(tmp_dir, exist_ok=True)
    pdf_path = os.path.join(tmp_dir, f"pdf_{id(url)}.pdf")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if b"%PDF" not in resp.content[:10] and "pdf" not in content_type.lower():
                return await _extract_article(url)

            with open(pdf_path, "wb") as f:
                f.write(resp.content)

        loop = asyncio.get_running_loop()
        title, text, segments = await loop.run_in_executor(
            None, _pymupdf_extract_structured_sync, pdf_path
        )

        if not text or not text.strip():
            return ExtractedContent(
                url=url,
                source_type="pdf",
                title="",
                content_text="",
                success=False,
                error="PDF contained no extractable text",
            )

        return ExtractedContent(
            url=url,
            source_type="pdf",
            title=title or "",
            content_text=text,
            segments=segments,
        )

    except Exception as e:
        logger.exception("PDF extraction failed for %s", url)
        return ExtractedContent(
            url=url,
            source_type="pdf",
            title="",
            content_text="",
            success=False,
            error=str(e),
        )
    finally:
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass


def _pymupdf_extract_sync(pdf_path: str) -> tuple[str, str]:
    """Extract title and text from a PDF file."""
    title, text, _segments = _pymupdf_extract_structured_sync(pdf_path)
    return title, text


def _pymupdf_extract_structured_sync(
    pdf_path: str,
) -> tuple[str, str, list[ExtractedSegment]]:
    """Extract ordered PDF text blocks with stable one-based page locators."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    title = doc.metadata.get("title", "") if doc.metadata else ""
    segments: list[ExtractedSegment] = []
    for page_index, page in enumerate(doc):
        blocks = sorted(page.get_text("blocks"), key=lambda block: (block[1], block[0]))
        for block in blocks:
            text = re.sub(r"\s+", " ", str(block[4] or "")).strip()
            if not text:
                continue
            segments.append(
                ExtractedSegment(
                    ordinal=len(segments),
                    text=text,
                    page_number=page_index + 1,
                    section_title=f"Page {page_index + 1}",
                )
            )
    doc.close()
    _with_character_offsets(segments)
    return title, "\n\n".join(segment.text for segment in segments), segments


async def _extract_article(url: str) -> ExtractedContent:
    """Extract content from article/blog URLs using trafilatura."""
    try:
        import trafilatura

        loop = asyncio.get_running_loop()
        downloaded = await loop.run_in_executor(None, trafilatura.fetch_url, url)

        if downloaded:
            text = await loop.run_in_executor(
                None,
                lambda: trafilatura.extract(
                    downloaded, include_tables=True, output_format="txt"
                ),
            )
            metadata = trafilatura.extract_metadata(downloaded)
            title = metadata.title if metadata and metadata.title else ""
            if text:
                segments = _article_segments_from_html(downloaded)
                return ExtractedContent(
                    url=url,
                    source_type="article",
                    title=title,
                    content_text=text,
                    segments=segments or _plain_segments(text, section_title=title or None),
                )

        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text

        text = await loop.run_in_executor(None, trafilatura.extract, html)

        if text:
            metadata = trafilatura.extract_metadata(html)
            title = metadata.title if metadata and metadata.title else ""
            segments = _article_segments_from_html(html)
            return ExtractedContent(
                url=url,
                source_type="article",
                title=title,
                content_text=text,
                segments=segments or _plain_segments(text, section_title=title or None),
            )

        return ExtractedContent(
            url=url,
            source_type="article",
            title="",
            content_text="",
            success=False,
            error="Could not extract text content",
        )

    except Exception as e:
        logger.exception("Article extraction failed for %s", url)
        return ExtractedContent(
            url=url,
            source_type="article",
            title="",
            content_text="",
            success=False,
            error=str(e),
        )


def _trafilatura_extract_sync(url: str) -> str | None:
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        return trafilatura.extract(downloaded, include_tables=True, output_format="txt")
    return None


class _ArticleSegmentParser(HTMLParser):
    """Small HTML structure parser for headings and paragraph-like blocks."""

    _BLOCK_TAGS = {"p", "li", "blockquote", "figcaption", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.heading_stack: list[str] = []
        self.items: list[tuple[str, list[str]]] = []
        self._capture_tag: str | None = None
        self._capture_level: int | None = None
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._capture_tag = tag
            self._capture_level = int(tag[1])
            self._parts = []
        elif tag in self._BLOCK_TAGS and self._capture_tag is None:
            self._capture_tag = tag
            self._capture_level = None
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav", "footer", "noscript"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return
        if self._ignored_depth or tag != self._capture_tag:
            return
        text = re.sub(r"\s+", " ", " ".join(self._parts)).strip()
        if self._capture_level is not None:
            if text:
                level = self._capture_level
                self.heading_stack = self.heading_stack[: level - 1]
                self.heading_stack.append(text)
        elif text:
            self.items.append((text, list(self.heading_stack)))
        self._capture_tag = None
        self._capture_level = None
        self._parts = []

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and self._capture_tag:
            clean = data.strip()
            if clean:
                self._parts.append(clean)


def _article_segments_from_html(payload: str) -> list[ExtractedSegment]:
    parser = _ArticleSegmentParser()
    try:
        parser.feed(payload)
    except Exception:
        return []
    segments = [
        ExtractedSegment(
            ordinal=index,
            text=text,
            section_title=headings[-1] if headings else None,
            heading_path=headings,
        )
        for index, (text, headings) in enumerate(parser.items)
    ]
    return _with_character_offsets(segments)


async def extract_from_file(
    file_path: str, source_type: str, whisper_model: str = "base"
) -> ExtractedContent:
    """Extract content from a local file (voice message, audio, video)."""
    try:
        timed = await transcribe_segments(file_path, model_size=whisper_model)
        segments = _with_character_offsets(
            [
                ExtractedSegment(
                    ordinal=index,
                    text=segment.text,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    speaker=segment.speaker,
                    caption_source=f"whisper:{whisper_model}",
                )
                for index, segment in enumerate(timed)
            ]
        )
        transcript = " ".join(segment.text for segment in segments)
        if segments:
            return ExtractedContent(
                url=None,
                source_type=source_type,
                title=f"Direct {source_type}",
                content_text=transcript,
                segments=segments,
            )
        return ExtractedContent(
            url=None,
            source_type=source_type,
            title="",
            content_text="",
            success=False,
            error="Transcription returned empty result",
        )
    except Exception as e:
        logger.exception("File extraction failed for %s", file_path)
        return ExtractedContent(
            url=None,
            source_type=source_type,
            title="",
            content_text="",
            success=False,
            error=str(e),
        )
