import json

import pytest

from markov_engine.bookmark_youtube import read_youtube


@pytest.mark.asyncio
async def test_available_captions_preserve_source_timing_and_metadata():
    player = {'videoDetails': {'videoId': 'abc', 'title': 'Persistent state', 'author': 'A creator',
        'thumbnail': {'thumbnails': [{'url': 'https://i.ytimg.com/vi/abc/default.jpg'}]}},
        'captions': {'playerCaptionsTracklistRenderer': {'captionTracks': [
            {'baseUrl': 'https://youtube.com/api/timedtext?v=abc&fmt=vtt', 'languageCode': 'en', 'kind': 'asr'}]}}}
    captions = {'events': [
        {'tStartMs': 1122000, 'dDurationMs': 2000, 'segs': [{'utf8': 'Persistent agent state.'}]},
        {'tStartMs': 1125000, 'dDurationMs': 2000, 'segs': [{'utf8': 'Keep a checkpoint.'}]},
        {'tStartMs': 1337000, 'dDurationMs': 4000, 'segs': [{'utf8': 'Replay recorded events.'}]},
    ]}
    calls = []

    async def fetch(url):
        calls.append(url)
        if 'timedtext' in url:
            assert 'fmt=json3' in url and 'fmt=vtt' not in url
            return json.dumps(captions).encode(), 'application/json', url
        return ('<script>var ytInitialPlayerResponse = ' + json.dumps(player) + ';</script>').encode(), 'text/html', url

    result = await read_youtube('https://youtube.com/watch?v=abc', fetch)
    assert result['title'] == 'Persistent state' and result['creator'] == 'A creator'
    assert result['content'] == result['transcript']
    assert result['important_passages'][0]['text'] == 'Persistent agent state. Keep a checkpoint.'
    assert result['important_passages'][0]['start_seconds'] == 1122
    assert result['important_passages'][1]['locator'] == '22:17'
    assert result['metadata']['automatic_captions']
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_unavailable_captions_keep_metadata_without_indexing_the_description():
    player = {'videoDetails': {'title': 'A saved video', 'shortDescription': 'This is not the transcript'}}

    async def fetch(url):
        return ('ytInitialPlayerResponse = ' + json.dumps(player)).encode(), 'text/html', url

    async def no_tracks(url):
        return []

    result = await read_youtube('https://youtube.com/watch?v=abc', fetch, find_tracks=no_tracks)
    assert result['title'] == 'A saved video'
    assert result['content'] == '' and 'Add a transcript' in result['processing_error']
    assert 'This is not the transcript' not in str(result)


@pytest.mark.asyncio
async def test_empty_page_captions_fall_back_to_the_original_language_track():
    # Page caption links that need a browser token answer 200 with an empty body.
    player = {'videoDetails': {'videoId': 'abc', 'title': 'Una charla', 'author': 'Canal'},
        'captions': {'playerCaptionsTracklistRenderer': {'captionTracks': [
            {'baseUrl': 'https://www.youtube.com/api/timedtext?v=abc&exp=xpe', 'languageCode': 'es'}]}}}
    captions = {'events': [{'tStartMs': 5000, 'dDurationMs': 2000, 'segs': [{'utf8': 'Hola a todos.'}]}]}
    calls, looked_up = [], []

    async def fetch(url):
        calls.append(url)
        if 'exp=xpe' in url:
            return b'', 'text/html', url
        if 'timedtext' in url:
            return json.dumps(captions).encode(), 'application/json', url
        return ('ytInitialPlayerResponse = ' + json.dumps(player)).encode(), 'text/html', url

    async def ytdlp_tracks(url):
        looked_up.append(url)
        return [
            {'baseUrl': 'https://www.youtube.com/api/timedtext?v=abc&lang=es&tlang=en', 'languageCode': 'en', 'kind': 'asr'},
            {'baseUrl': 'https://www.youtube.com/api/timedtext?v=abc&lang=es&kind=asr', 'languageCode': 'es', 'kind': 'asr'},
        ]

    result = await read_youtube('https://youtube.com/watch?v=abc', fetch, find_tracks=ytdlp_tracks)
    assert looked_up == ['https://youtube.com/watch?v=abc']
    assert result['content'] == 'Hola a todos.' and 'processing_error' not in result
    assert result['metadata']['caption_language'] == 'es' and result['metadata']['automatic_captions']
    assert result['important_passages'][0]['locator'] == '0:05'
    assert not any('tlang=' in url for url in calls)


@pytest.mark.asyncio
async def test_page_captions_that_work_skip_the_fallback_lookup():
    player = {'captions': {'playerCaptionsTracklistRenderer': {'captionTracks': [
        {'baseUrl': 'https://www.youtube.com/api/timedtext?v=abc', 'languageCode': 'en'}]}}}
    captions = {'events': [{'tStartMs': 0, 'segs': [{'utf8': 'Hello.'}]}]}

    async def fetch(url):
        if 'timedtext' in url:
            return json.dumps(captions).encode(), 'application/json', url
        return ('ytInitialPlayerResponse = ' + json.dumps(player)).encode(), 'text/html', url

    async def unexpected(url):
        raise AssertionError('yt-dlp should not run when page captions work')

    result = await read_youtube('https://youtube.com/watch?v=abc', fetch, find_tracks=unexpected)
    assert result['content'] == 'Hello.'
