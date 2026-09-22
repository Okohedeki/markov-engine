"""Read-only illustrative archive; never inserted into a user's real collection."""
import datetime as dt
from urllib.parse import urlsplit


def example_archive():
    current = dt.datetime.now(dt.timezone.utc)
    examples = [
        ('reward-hacking', 'Reward Hacking in Reinforcement Learning',
         'https://lilianweng.github.io/posts/2024-11-28-reward-hacking/', 'Lilian Weng', 'article', 240,
         'A reminder that a better score can hide a worse outcome. Come back to this when designing agent evals.',
         ['Agent evaluation', 'Reward hacking', 'Reliable AI-generated code']),
        ('effective-agents', 'Building effective agents',
         'https://www.anthropic.com/engineering/building-effective-agents', 'Anthropic', 'article', 1,
         'Start simple. Keep the workflow understandable before adding autonomy.',
         ['Agent evaluation', 'Tool control', 'Reliable AI-generated code']),
        ('evals', 'openai / evals', 'https://github.com/openai/evals', 'OpenAI', 'github', 2,
         'A useful reference for testing model behavior against examples we actually care about.',
         ['Agent evaluation', 'Behavioral verification', 'Reliable AI-generated code']),
        ('tools', 'Tools — Model Context Protocol',
         'https://modelcontextprotocol.io/specification/2025-11-25/server/tools', 'MCP', 'webpage', 3,
         'Tool descriptions, schemas, and permissions belong together.',
         ['Tool control', 'Agent evaluation', 'Runtime permissions']),
        ('authorization', 'Authorization — Model Context Protocol',
         'https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization', 'MCP', 'webpage', 80,
         'Keep this around for the connector authentication work.',
         ['Runtime permissions', 'Tool control', 'OAuth']),
    ]
    items = []
    for identity, title, url, author, kind, age, note, concepts in examples:
        items.append(dict(bookmark_id=identity, user_id='example', canonical_url=url, original_url=url,
            title=title, author=author, creator=author, source_type=kind, source_domain=urlsplit(url).hostname,
            saved_at=(current - dt.timedelta(days=age)).isoformat(), published_at=None,
            user_note=note, inferred_save_reason='', summary='', content='', transcript='',
            metadata={'content_origin': 'Read-only example. The notes and activity are illustrative.'},
            concepts=concepts, entities=[author], thumbnail='', important_passages=[], timestamps=[],
            embeddings=[], claims=[], relationships=[], thread_memberships=[], project_memberships=[],
            relevance_events=[], resurface_history=[], view_history=[], favorite_state=age > 30,
            archive_state=False, processing_state='ready', processing_error=''))
    return sorted(items, key=lambda item: item['saved_at'], reverse=True)


async def example_page(params):
    from markov_engine.bookmark_intelligence import search_archive
    from markov_engine.bookmark_views import archive_context, filter_archive, source_context
    items = example_archive()
    screen = params.get('view', 'home')
    screen = screen if screen in {'home', 'library', 'threads', 'search', 'you', 'projects'} else 'home'
    context = archive_context(items, screen=screen, demo=True)
    template = 'memory_' + screen + '.html'
    if params.get('item') and screen != 'search':
        item = next((item for item in items if item['bookmark_id'] == params['item']), items[0])
        item, text = source_context(item)
        context.update(item=item, export_text=text, memberships=[row for row in context['threads']
            if item['bookmark_id'] in row['bookmark_ids']], page_title='Example save')
        template = 'memory_detail.html'
    elif params.get('thread'):
        thread = next((row for row in context['threads'] if row['id'] == params['thread']), context['threads'][0])
        context.update(thread=thread, related=[], page_title=thread['title'])
        template = 'memory_thread.html'
    elif screen == 'library':
        context.update(filtered=filter_archive(items, params, context['threads']), params=params,
            sources=sorted({item['source_domain'] for item in items}),
            types=sorted({item['source_type'] for item in items}),
            view=params.get('layout') if params.get('layout') in {'cards', 'compact', 'visual'} else 'cards')
    elif screen in {'threads', 'projects'}:
        context['rows'] = context[screen]
        template = 'memory_threads.html'
    elif screen == 'search':
        # Public examples never trigger paid embedding or model calls.
        query = params.get('q', '')[:1000]
        results, label = await search_archive(items, query, 'exact')
        context.update(query=query, results=results, search_label='Example archive · exact search',
            mode='exact', answer=None, types=sorted({item['source_type'] for item in items}),
            source_type='', scoped_item='', compare='')
    elif screen == 'you':
        context.update(favorites=sum(item['favorite_state'] for item in items), revisited=0,
                       hidden_collections=[], search_status='This read-only example uses exact search.')
    return template, context
