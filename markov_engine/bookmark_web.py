"""Authenticated bookmark routes using Markov's existing identity boundary."""
import datetime as dt
import json
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from markov_engine.bookmark_views import archive_context


async def bookmark_form(request):
    origin = request.headers.get('origin')
    if ((origin and origin.rstrip('/') != str(request.base_url).rstrip('/'))
            or request.headers.get('sec-fetch-site') == 'cross-site'):
        raise HTTPException(403, 'Cross-origin changes are not accepted.')
    if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
        raise HTTPException(415, 'Submit this form using URL-encoded fields.')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 2_000_000:
            raise HTTPException(413, 'This source is too large. Save the link first, then add a shorter excerpt.')
    values = parse_qs(raw.decode('utf-8', errors='replace'), keep_blank_values=True)
    return {key: values[-1] for key, values in values.items()}


def create_bookmark_router(*, owner, render):
    router = APIRouter()

    @router.get('/app/memory')
    @router.get('/app')
    async def home(request: Request):
        try:
            identity = owner(request)
        except HTTPException:
            return RedirectResponse('/app/login', 303)
        archive = request.app.state.store.bookmarks
        context = archive_context(await archive.items(identity), await archive.collections(identity))
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        for item in context['resurfaced']:
            if not any(event['at'].startswith(today) for event in item['resurface_history']):
                await archive.record_event(identity, item['bookmark_id'], 'resurface_history', item['resurface_reason'])
        response = render(request, 'memory_home.html', **context)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @router.post('/app/bookmarks')
    async def capture(request: Request):
        identity = owner(request)
        values = await bookmark_form(request)
        try:
            item, created = await request.app.state.store.bookmarks.save(identity, values.get('url', ''),
                title=values.get('title', ''), note=values.get('note', ''), content=values.get('content', ''))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        destination = '/app/bookmarks/' + item['bookmark_id']
        if 'application/json' in request.headers.get('accept', ''):
            return JSONResponse({'created': created, 'url': destination, 'bookmark_id': item['bookmark_id']},
                                status_code=201 if created else 200)
        return RedirectResponse(destination + '?saved=1', 303)

    @router.get('/app/library')
    async def library(request: Request):
        identity = owner(request)
        from markov_engine.bookmark_views import filter_archive
        archive = request.app.state.store.bookmarks
        items = await archive.items(identity)
        context = archive_context(items, await archive.collections(identity), 'library')
        context.update(filtered=filter_archive(items, request.query_params, context['threads'] + context['projects']),
            sources=sorted({item['source_domain'] for item in items}),
            types=sorted({item['source_type'] for item in items}), params=request.query_params,
            view=request.query_params.get('layout') if request.query_params.get('layout') in {'cards', 'compact', 'visual'} else 'cards')
        return render(request, 'memory_library.html', **context)

    @router.get('/app/bookmarks/{bookmark_id}')
    async def detail(bookmark_id: str, request: Request):
        identity = owner(request)
        from markov_engine.bookmark_views import source_context
        archive = request.app.state.store.bookmarks
        items = await archive.items(identity)
        item = next((row for row in items if row['bookmark_id'] == bookmark_id), None)
        if item is None:
            raise HTTPException(404, 'This save was not found in your archive.')
        await archive.record_event(identity, bookmark_id, 'view_history')
        context = archive_context(items, await archive.collections(identity), 'library')
        item, export_text = source_context(item)
        context.update(item=item, export_text=export_text,
            memberships=[row for row in context['threads'] + context['projects']
                         if bookmark_id in {member['bookmark_id'] for member in row['items']}],
            notice='Saved to Markov. Your link and thought are safe.' if request.query_params.get('saved') else '',
            page_title='Saved source')
        return render(request, 'memory_detail.html', **context)

    @router.post('/app/bookmarks/{bookmark_id}/edit')
    async def edit(bookmark_id: str, request: Request):
        identity = owner(request)
        values = await bookmark_form(request)
        archive = request.app.state.store.bookmarks
        rows = await archive.items(identity, bookmark_id)
        if not rows:
            raise HTTPException(404, 'Save not found.')
        item, action = rows[0], values.get('action')
        if action in {'favorite', 'archive'}:
            changes = {action + '_state': values.get('value') == 'true'}
        elif action == 'note':
            changes = {'user_note': values.get('note', '')[:8000]}
        elif action == 'reason':
            changes = {'inferred_save_reason': values.get('reason', '')[:1000], 'reason_edited': True}
        elif action == 'content':
            if not values.get('content', '').strip():
                raise HTTPException(422, 'Add source text before saving.')
            changes = {'content': values['content'][:500_000], 'supplied_content': True,
                       'processing_state': 'pending', 'processing_error': '', 'important_passages': []}
        elif action == 'retry':
            changes = {'processing_state': 'pending', 'processing_error': ''}
        else:
            raise HTTPException(422, 'Unknown bookmark action.')
        if item['processing_state'] == 'processing' and action in {'content', 'retry'}:
            raise HTTPException(409, 'This save is being processed. Try again when it finishes.')
        await archive.update(identity, bookmark_id, changes)
        if 'application/json' in request.headers.get('accept', ''):
            return {'ok': True, 'action': action}
        return RedirectResponse('/app/bookmarks/' + bookmark_id, 303)

    @router.get('/app/bookmarks/{bookmark_id}/export')
    async def export_one(bookmark_id: str, request: Request):
        from markov_engine.bookmark_views import source_context
        rows = await request.app.state.store.bookmarks.items(owner(request), bookmark_id)
        if not rows:
            raise HTTPException(404, 'Save not found.')
        _, content = source_context(rows[0])
        return Response(content, media_type='text/markdown', headers={
            'Content-Disposition': f'attachment; filename="markov-{rows[0]["bookmark_id"]}.md"',
            'Cache-Control': 'no-store',
        })

    @router.get('/app/memory/search')
    @router.get('/app/search')
    async def search(request: Request):
        from markov_engine.bookmark_intelligence import ask_saved, search_archive
        identity = owner(request)
        archive = request.app.state.store.bookmarks
        items = await archive.items(identity)
        context = archive_context(items, await archive.collections(identity), 'search')
        params = request.query_params
        query = params.get('q', '').strip()[:1000]
        mode = params.get('mode', 'hybrid')
        mode = mode if mode in {'exact', 'hybrid', 'semantic'} else 'hybrid'
        selected = [item for item in items if not item['archive_state']]
        scoped = {value for value in [params.get('item'), params.get('compare')] if value}
        if scoped:
            selected = [item for item in selected if item['bookmark_id'] in scoped]
        if params.get('type'):
            selected = [item for item in selected if item['source_type'] == params['type']]
        results, label = await search_archive(selected, query, mode)
        answer = None
        if params.get('ask') and query:
            answer = await ask_saved(query, selected if scoped else results)
            if scoped:
                results = selected
        context.update(query=query, mode=mode, results=results, search_label=label, answer=answer,
            scoped_item=params.get('item', ''), compare=params.get('compare', ''),
            types=sorted({item['source_type'] for item in items}), source_type=params.get('type', ''))
        return render(request, 'memory_search.html', **context)

    @router.get('/app/threads')
    @router.get('/app/projects')
    async def collections_page(request: Request):
        identity = owner(request)
        archive = request.app.state.store.bookmarks
        screen = 'projects' if request.url.path.endswith('/projects') else 'threads'
        context = archive_context(await archive.items(identity), await archive.collections(identity), screen)
        return render(request, 'memory_threads.html', rows=context[screen], **context)

    @router.get('/app/threads/{collection_id}')
    async def collection_page(collection_id: str, request: Request):
        identity = owner(request)
        archive = request.app.state.store.bookmarks
        context = archive_context(await archive.items(identity), await archive.collections(identity), 'threads')
        thread = next((row for row in context['threads'] + context['projects'] if row['id'] == collection_id), None)
        if thread is None:
            raise HTTPException(404, 'Collection not found. Hidden collections can be restored from You.')
        related = []
        if thread['kind'] == 'project':
            concepts = {value for item in thread['items'] for value in item['concepts']}
            members = {item['bookmark_id'] for item in thread['items']}
            related = [item for item in context['items'] if item['bookmark_id'] not in members
                       and concepts & set(item['concepts'])][:5]
        context.update(thread=thread, related=related, page_title=thread['title'],
                       screen='projects' if thread['kind'] == 'project' else 'threads')
        return render(request, 'memory_thread.html', **context)

    @router.post('/app/collections')
    async def change_collection(request: Request):
        import uuid
        identity = owner(request)
        values = await bookmark_form(request)
        archive = request.app.state.store.bookmarks
        items, stored = await archive.items(identity), await archive.collections(identity)
        context = archive_context(items, stored)
        all_rows = {row['id']: row for row in stored + context['threads'] + context['projects']}
        action, row_id = values.get('action'), values.get('id')
        fields = {'id', 'title', 'kind', 'automatic', 'topic', 'bookmark_ids', 'excluded_ids',
                  'pinned', 'hidden', 'notes', 'questions'}
        if action == 'create':
            row = {'id': uuid.uuid4().hex, 'kind': values.get('kind', 'thread'),
                   'title': values.get('title', '').strip()[:120], 'automatic': False,
                   'bookmark_ids': [], 'excluded_ids': [], 'pinned': False, 'hidden': False}
            if not row['title'] or row['kind'] not in {'thread', 'project'}:
                raise HTTPException(422, 'Choose a collection name and type.')
        else:
            if row_id not in all_rows:
                raise HTTPException(404, 'Collection not found.')
            row = {key: value for key, value in all_rows[row_id].items() if key in fields}
            if action == 'rename':
                row['title'] = values.get('title', '').strip()[:120]
                if not row['title']:
                    raise HTTPException(422, 'A collection needs a name.')
            elif action in {'pin', 'hide', 'restore'}:
                field = 'pinned' if action == 'pin' else 'hidden'
                row[field] = not row.get(field, False) if action == 'pin' else action == 'hide'
            elif action == 'notes':
                row.update(notes=values.get('notes', '')[:8000], questions=values.get('questions', '')[:4000])
            elif action in {'add', 'remove'}:
                bookmark_id = values.get('bookmark_id')
                if bookmark_id not in {item['bookmark_id'] for item in items}:
                    raise HTTPException(404, 'Save not found.')
                ids, excluded = set(row.get('bookmark_ids', [])), set(row.get('excluded_ids', []))
                if action == 'add':
                    ids.add(bookmark_id)
                    excluded.discard(bookmark_id)
                else:
                    ids.discard(bookmark_id)
                    excluded.add(bookmark_id)
                row.update(bookmark_ids=sorted(ids), excluded_ids=sorted(excluded))
            elif action == 'merge':
                target = all_rows.get(values.get('target'))
                if not target or target['id'] == row['id'] or target['kind'] != row['kind']:
                    raise HTTPException(422, 'Choose a different collection of the same type.')
                target = {key: value for key, value in target.items() if key in fields}
                target['bookmark_ids'] = sorted(set(target.get('bookmark_ids', []) + row.get('bookmark_ids', [])))
                await archive.collections(identity, collection=target)
                row['hidden'] = True
            elif action == 'split':
                selected = {key.removeprefix('pick_') for key in values if key.startswith('pick_')}
                selected &= set(row.get('bookmark_ids', []))
                title = values.get('title', '').strip()[:120]
                if not selected or not title:
                    raise HTTPException(422, 'Select saves and name the new collection.')
                new_row = {**row, 'id': uuid.uuid4().hex, 'title': title, 'automatic': False,
                           'bookmark_ids': sorted(selected), 'excluded_ids': []}
                await archive.collections(identity, collection=new_row)
                row['bookmark_ids'] = sorted(set(row.get('bookmark_ids', [])) - selected)
                row['excluded_ids'] = sorted(set(row.get('excluded_ids', [])) | selected)
            else:
                raise HTTPException(422, 'Unknown collection action.')
        await archive.collections(identity, collection=row)
        destination = '/app/threads/' + row['id']
        if row.get('hidden'):
            destination = '/app/projects' if row['kind'] == 'project' else '/app/threads'
        return RedirectResponse(destination, 303)

    @router.get('/app/you')
    async def you(request: Request):
        from markov_engine.config import get_settings
        identity = owner(request)
        archive = request.app.state.store.bookmarks
        items, collections = await archive.items(identity), await archive.collections(identity)
        context = archive_context(items, collections, 'you')
        return render(request, 'memory_you.html', **context,
            favorites=sum(item['favorite_state'] for item in items),
            revisited=sum(bool(item['view_history']) for item in items),
            hidden_collections=[row for row in collections if row.get('hidden')],
            search_status='Keyword search is available. Configure an embedding provider for semantic retrieval.'
                if get_settings().embed_backend == 'hash' else
                'Semantic indexing is configured. Keyword search remains available if the provider is unavailable.')

    @router.get('/app/archive/export')
    async def export_archive(request: Request):
        identity = owner(request)
        archive = request.app.state.store.bookmarks
        payload = {'format': 'markov-bookmarks-v1', 'exported_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'bookmarks': await archive.items(identity), 'collections': await archive.collections(identity)}
        return Response(json.dumps(payload, ensure_ascii=False, indent=2), media_type='application/json',
            headers={'Content-Disposition': 'attachment; filename="markov-archive.json"', 'Cache-Control': 'no-store'})

    @router.get('/app/manifest.webmanifest')
    async def manifest():
        return JSONResponse({'id': '/app', 'name': 'Markov — Personal memory', 'short_name': 'Markov',
            'description': 'Save anything worth remembering. Find it when it matters.',
            'start_url': '/app', 'scope': '/app', 'display': 'standalone',
            'background_color': '#f7f5ef', 'theme_color': '#f7f5ef',
            'icons': [{'src': '/static/markov-mark.svg', 'sizes': 'any', 'type': 'image/svg+xml', 'purpose': 'any'}],
            'share_target': {'action': '/app/share', 'method': 'GET',
                             'params': {'title': 'title', 'text': 'text', 'url': 'url'}}},
            media_type='application/manifest+json')

    @router.get('/app/share')
    async def receive_share(request: Request):
        import re
        params = request.query_params
        text = params.get('text', '')[:8000]
        shared_url = params.get('url', '')[:8192]
        if not shared_url:
            match = re.search(r'https?://\S+', text)
            if match:
                shared_url = match.group(0)
                text = text.replace(shared_url, '').strip()
        try:
            owner(request)
            signed_in = True
        except HTTPException:
            signed_in = False
        return render(request, 'memory_share.html', signed_in=signed_in,
            shared_url=shared_url, shared_title=params.get('title', '')[:500], shared_text=text)

    return router
