"""Read publicly exposed YouTube metadata and captions without downloading media."""
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from markov_engine.bookmark_urls import canonicalize


async def read_youtube(url, fetch):
    from markov_engine.extract import _parse_json3_segments
    body, _, final_url = await fetch(url)
    html = body.decode('utf-8', errors='replace')
    match = re.search(r'(?:var\s+)?ytInitialPlayerResponse\s*=\s*', html)
    if not match:
        return {'content': '', 'processing_error':
            'The video is saved. Public captions are unavailable; add a transcript to search its contents.'}
    player, _ = json.JSONDecoder().raw_decode(html[match.end():])
    details = player.get('videoDetails', {})
    result = {'content': '', 'source_type': 'youtube', 'metadata': {
        'extracted_from': final_url, 'video_id': details.get('videoId', ''),
        'duration_seconds': details.get('lengthSeconds', ''),
        'content_origin': 'Public YouTube captions'}}
    if details.get('title'):
        result['title'] = str(details['title'])[:500]
    result['author'] = result['creator'] = str(details.get('author', ''))[:500]
    images = details.get('thumbnail', {}).get('thumbnails', [])
    if images:
        try:
            result['thumbnail'] = canonicalize(images[-1]['url'])
        except (ValueError, KeyError):
            pass
    tracks = player.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
    tracks = [track for track in tracks if isinstance(track.get('baseUrl'), str)]
    if tracks:
        tracks.sort(key=lambda track: (not str(track.get('languageCode', '')).startswith('en'),
                                       track.get('kind') == 'asr'))
        track = tracks[0]
        parsed = urlsplit(track['baseUrl'])
        query = [(key, value) for key, value in parse_qsl(parsed.query) if key != 'fmt']
        caption_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                 urlencode(query + [('fmt', 'json3')]), ''))
        try:
            captions, _, _ = await fetch(caption_url)
            segments = _parse_json3_segments(captions.decode('utf-8'), caption_source='youtube')
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
            if text:
                result.update(content=text, transcript=text, important_passages=passages[:120])
                result['metadata'].update(caption_language=track.get('languageCode', ''),
                                          automatic_captions=track.get('kind') == 'asr')
                return result
        except Exception:
            # Keep the title and creator even when a caption endpoint rejects access.
            pass
    result['processing_error'] = (
        'The video and available metadata are saved. Add a transcript to make its contents searchable.')
    return result
