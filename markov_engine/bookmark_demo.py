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
