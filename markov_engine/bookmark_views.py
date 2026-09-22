"""Presentation data for the personal archive, shared by the app and labeled demo."""
import datetime as dt

from markov_engine.bookmark_intelligence import archive_threads, rediscover


def archive_context(items, collections=(), screen='home', demo=False):
    active = [item for item in items if not item['archive_state']]
    threads = archive_threads(active, [row for row in collections if row['kind'] == 'thread'])
    projects = archive_threads(active, [row for row in collections if row['kind'] == 'project'])
    projects = [row for row in projects if row['kind'] == 'project']
    navigation = {key: '/app' + ('' if key == 'home' else '/' + key)
                  for key in ['home', 'library', 'threads', 'search', 'you', 'projects']}
    if demo:
        navigation = {key: '/demo?view=' + key for key in navigation}
    return dict(items=active, all_items=items, threads=threads, projects=projects,
        resurfaced=rediscover(active), attention=max(threads, key=lambda row: row['count'], default=None),
        nav_urls=navigation, demo=demo, screen=screen, page_title=screen.capitalize(),
        today=dt.datetime.now().strftime('%A, %B %d'), notice='', query='', view='cards')


def filter_archive(items, params, collections=()):
    selected = list(items)
    state = params.get('state', '')
    selected = [item for item in selected if item['archive_state'] == (state == 'archived')]
    for key, field in [('source', 'source_domain'), ('type', 'source_type')]:
        if params.get(key):
            selected = [item for item in selected if item[field] == params[key]]
    for key, field in [('topic', 'concepts'), ('person', 'entities')]:
        if params.get(key):
            needle = params[key].casefold()
            selected = [item for item in selected if any(needle in value.casefold() for value in item[field])
                        or (key == 'person' and needle in item['author'].casefold())]
    if state == 'favorite':
        selected = [item for item in selected if item['favorite_state']]
    elif state in {'unread', 'revisited'}:
        selected = [item for item in selected if bool(item['view_history']) == (state == 'revisited')]
    elif state == 'resurfaced':
        selected = [item for item in selected if item['resurface_history']]
    elif state == 'processing':
        selected = [item for item in selected if item['processing_state'] in {'pending', 'processing'}]
    elif state == 'partial':
        selected = [item for item in selected if item['processing_state'] == 'partial']
    if params.get('after'):
        selected = [item for item in selected if item['saved_at'][:10] >= params['after']]
    if params.get('before'):
        selected = [item for item in selected if item['saved_at'][:10] <= params['before']]
    if params.get('collection'):
        collection = next((row for row in collections if row['id'] == params['collection']), {})
        allowed = {item['bookmark_id'] for item in collection.get('items', [])}
        selected = [item for item in selected if item['bookmark_id'] in allowed]
    if params.get('q'):
        query = params['q'].casefold()
        selected = [item for item in selected if query in ' '.join([
            item['title'], item['user_note'], item['content'], item['inferred_save_reason']]).casefold()]
    sort = params.get('sort', 'recent')
    if sort == 'forgotten':
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
        selected = [item for item in selected if item['saved_at'] < cutoff
                    and (item['favorite_state'] or item['user_note'] or item['inferred_save_reason'])
                    and (not item['view_history'] or item['view_history'][-1]['at'] < cutoff)]
    def sort_key(item):
        if sort == 'relevant':
            return (item['resurface_history'][-1]['at'] if item['resurface_history'] else '', item['saved_at'])
        if sort == 'revisited':
            return len(item['view_history']), item['saved_at']
        if sort == 'connected':
            return sum(bool(set(item['concepts']) & set(other['concepts'])) for other in items
                       if other['bookmark_id'] != item['bookmark_id']), item['saved_at']
        return item['saved_at']
    return sorted(selected, key=sort_key, reverse=sort not in {'oldest', 'forgotten'})


def source_context(item):
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    passages = []
    for passage in item['important_passages']:
        url = item['canonical_url']
        if passage.get('start_seconds') is not None and item['source_domain'] == 'youtube.com':
            parts = urlsplit(url)
            query = dict(parse_qsl(parts.query))
            query['t'] = str(max(0, int(passage['start_seconds'])))
            url = urlunsplit(parts._replace(query=urlencode(query)))
        elif passage.get('page_number'):
            url += '#page=' + str(passage['page_number'])
        passages.append({**passage, 'url': url})
    lines = [f'# {item["title"]}', '', f'Source: {item["canonical_url"]}',
             f'Saved: {item["saved_at"]}', '', '## User note', item['user_note'] or '(none)',
             '', '## Markov interpretation', item['inferred_save_reason'] or '(none)', item['summary']]
    for passage in passages:
        lines.extend(['', f'## {passage["locator"]} ({passage.get("origin", "source")})',
                      passage['text'], passage['url']])
    return {**item, 'important_passages': passages}, '\n'.join(lines)
