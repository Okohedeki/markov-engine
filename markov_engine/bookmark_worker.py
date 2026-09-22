"""Durable queue consumer; capture succeeds independently of enrichment."""
import asyncio
import logging

from markov_engine.bookmark_extract import read_source
from markov_engine.bookmark_intelligence import interpret
from markov_engine.config import get_settings

logger = logging.getLogger(__name__)


async def process_bookmark(archive, item):
    from markov_engine.embeddings import embed
    owner, identity = item['user_id'], item['bookmark_id']
    try:
        extracted = await asyncio.wait_for(read_source(item), timeout=50)
        await archive.update(owner, identity, extracted)
        enriched = {**item, **extracted}
        interpretation = await interpret(enriched)
        latest = await archive.items(owner, identity)
        if latest and latest[0].get('reason_edited'):
            interpretation.pop('inferred_save_reason', None)
        await archive.update(owner, identity, interpretation)
        enriched.update(interpretation)
        settings = get_settings()
        vector_patch = {'embeddings': [], 'embedding_model': '', 'index_mode': 'keyword'}
        if settings.embed_backend != 'hash':
            try:
                vector = await asyncio.wait_for(embed('\n'.join([
                    enriched['title'], enriched['user_note'], enriched['inferred_save_reason'],
                    ' '.join(enriched['concepts']), enriched['content'][:18000],
                ])), timeout=20)
                vector_patch = {'embeddings': vector, 'index_mode': 'semantic',
                    'embedding_model': f'{settings.embed_backend}:{settings.embed_model}:{settings.openai_embed_model}'}
            except Exception:
                pass  # Lexical retrieval and the saved source remain available.
        await archive.update(owner, identity, {**vector_patch,
            'processing_state': 'ready' if enriched.get('content') else 'partial',
            'processing_error': enriched.get('processing_error', '')})
    except asyncio.CancelledError:
        await archive.update(owner, identity, {'processing_state': 'pending'})
        raise
    except Exception:
        logger.info('Bookmark extraction unavailable for %s', identity)
        await archive.update(owner, identity, {'processing_state': 'partial', 'processing_error':
            "Article text couldn't be extracted. The URL and your note were still saved. You can retry or add text."})


async def run_bookmark_worker(archive):
    while True:
        try:
            item = await archive.claim_pending()
            if item:
                await process_bookmark(archive, item)
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Bookmark queue will retry after a storage error')
            await asyncio.sleep(5)
