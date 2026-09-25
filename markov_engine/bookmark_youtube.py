"""Read publicly exposed YouTube metadata and captions without downloading media."""
import asyncio
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from markov_engine.bookmark_urls import public_url


async def ytdlp_caption_tracks(url):
    """Caption links from yt-dlp, whose player clients still receive usable caption URLs."""
    from markov_engine.extract import _ytdlp_info_sync
    try:
        info = await asyncio.wait_for(asyncio.to_thread(_ytdlp_info_sync, url), timeout=30)
    except Exception:
        return []
    tracks = []
    for key, kind in (('subtitles', ''), ('automatic_captions', 'asr')):
        for language, formats in ((info or {}).get(key) or {}).items():
            for fmt in formats or []:
                if fmt.get('ext') == 'json3' and isinstance(fmt.get('url'), str):
                    tracks.append({'baseUrl': fmt['url'], 'languageCode': language, 'kind': kind})
    return tracks


def _ranked(tracks):
    # Prefer the video's own words: untranslated, English, then human captions.
    tracks = [track for track in tracks if isinstance(track.get('baseUrl'), str)]
    return sorted(tracks, key=lambda track: ('tlang=' in track['baseUrl'],
        not str(track.get('languageCode', '')).startswith('en'), track.get('kind') == 'asr'))


async def _read_track(track, fetch, url):
    from markov_engine.extract import _parse_json3_segments
    parsed = urlsplit(track['baseUrl'])
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key != 'fmt']
    caption_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                             urlencode(query + [('fmt', 'json3')]), ''))
    try:
        captions, _, _ = await fetch(caption_url)
        segments = _parse_json3_segments(captions.decode('utf-8'), caption_source='youtube')
    except Exception:
        # An empty or rejected caption response leaves the saved video intact.
        return None
    passages = []
    for segment in segments:
        start = max(0, int(segment.start_seconds or 0))
        # Group short caption cues into readable, timestamped source passages.
        if passages and start - passages[-1]['start_seconds'] < 30:
            passages[-1]['text'] += ' ' + segment.text
        else:
            passages.append({'text': segment.text, 'start_seconds': start,
                'locator': f'{start // 60}:{start % 60:02}', 'source_url': url, 'origin': 'source'})
    text = '\n'.join(segment.text for segment in segments)[:500_000]
    return (text, passages[:120]) if text else None


async def read_youtube(url, fetch, find_tracks=None):
    body, _, final_url = await fetch(url)
    html = body.decode('utf-8', errors='replace')
    match = re.search(r'(?:var\s+)?ytInitialPlayerResponse\s*=\s*', html)
    player = json.JSONDecoder().raw_decode(html[match.end():])[0] if match else {}
    details = player.get('videoDetails', {})
    result = {'content': '', 'source_type': 'youtube', 'metadata': {
        'extracted_from': final_url, 'video_id': details.get('videoId', ''),
        'duration_seconds': details.get('lengthSeconds', ''),
        'content_origin': 'Public YouTube captions'}}
    if details.get('title'):
        result['title'] = str(details['title'])[:500]
    if details.get('author'):
        result['author'] = result['creator'] = str(details['author'])[:500]
    images = details.get('thumbnail', {}).get('thumbnails', [])
    if images:
        try:
            result['thumbnail'] = public_url(images[-1]['url'])
        except (ValueError, KeyError):
            pass
    page_tracks = player.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
    # Page caption links can require a browser proof-of-origin token and then return
    # an empty body, so fall back to yt-dlp's links before asking for a transcript.
    for source in ('page', 'yt-dlp'):
        tracks = page_tracks if source == 'page' else await (find_tracks or ytdlp_caption_tracks)(url)
        for track in _ranked(tracks)[:2]:
            captured = await _read_track(track, fetch, url)
            if captured:
                text, passages = captured
                result.update(content=text, transcript=text, important_passages=passages)
                result['metadata'].update(caption_language=track.get('languageCode', ''),
                                          automatic_captions=track.get('kind') == 'asr')
                return result
    result['processing_error'] = (
        'The video and available metadata are saved. Add a transcript to make its contents searchable.')
    return result
