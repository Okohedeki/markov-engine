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
