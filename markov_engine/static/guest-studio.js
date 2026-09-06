(() => {
  'use strict';
  const root = document.querySelector('.guest-page [data-idea-playground]');
  const studio = root?.markovPlayground;
  if (!studio) return;
  const links = [...document.querySelectorAll('[data-guest-view]')];
  const library = root.querySelector('[data-guest-drafts]');
  const heading = document.querySelector('[data-guest-title]');
  const description = document.querySelector('[data-guest-description]');
  const resetDialog = document.querySelector('[data-guest-reset-dialog]');
  const formats = {post: 'Short post', thread: 'Thread', video: 'Video outline'};
  const views = {
    studio: ['Find your next batch of ideas.', 'Choose a conversation below. Explore different angles, then keep the ones that feel like you.'],
    shortlist: ['Good ideas, kept together.', 'Your favorite angles across every conversation. Develop one, or export your whole batch.'],
    drafts: ['Something worth posting.', 'Your saved working drafts. Keep writing, try a different format, or take them into your publishing flow.']
  };
  let view = views[location.hash.slice(1)] ? location.hash.slice(1) : 'studio';
  const make = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  const download = () => {
    const state = studio.state();
    const pieces = Object.entries(state.drafts).map(([id, kind]) => {
      const record = state.records.find(item => item.id === id);
      return `## ${record.hook}\n\n${formats[kind]} · ${record.topic.category}\n\n${state.textFor(record, kind)}`;
    });
    const blob = new Blob([`# Markov guest drafts\n\nYour saved edits to prewritten examples. Verify factual claims before posting.\n\n${pieces.join('\n\n---\n\n')}\n`], {type: 'text/markdown;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = make('a');
    link.href = url; link.download = 'markov-drafts.md'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const renderDrafts = () => {
    const state = studio.state();
    const entries = Object.entries(state.drafts);
    library.replaceChildren();
    const toolbar = make('div', undefined, 'guest-draft-toolbar');
    const exportButton = make('button', 'Export drafts ↓', 'mk-button mk-button-quiet');
    exportButton.type = 'button'; exportButton.dataset.exportDrafts = ''; exportButton.disabled = !entries.length;
    exportButton.addEventListener('click', download);
    toolbar.append(make('p', `${entries.length} saved ${entries.length === 1 ? 'draft' : 'drafts'} · Stored in this browser`), exportButton);
    library.append(toolbar);
    if (!entries.length) {
      const empty = make('div', undefined, 'guest-empty');
      const icon = make('span', '▤'); icon.setAttribute('aria-hidden', 'true');
      const action = make('button', 'Find an idea to develop →', 'mk-button mk-button-primary');
      action.type = 'button'; action.addEventListener('click', () => navigate('studio', true));
      empty.append(icon, make('h2', 'Your next post starts with an angle.'), make('p', 'Open an idea, make the outline your own, and choose Save draft. It will be waiting for you here.'), action);
      library.append(empty);
      return;
    }
    const list = make('div', undefined, 'guest-draft-list');
    entries.forEach(([id, kind]) => {
      const record = state.records.find(item => item.id === id);
      const card = make('article', undefined, 'guest-draft');
      const text = state.textFor(record, kind);
      const open = make('button', 'Continue writing ↗', 'mk-button mk-button-quiet');
      open.type = 'button'; open.dataset.guestDraft = id;
      open.setAttribute('aria-label', `Continue writing: ${record.hook}`);
      open.addEventListener('click', () => studio.open(id, kind));
      card.append(make('span', `${formats[kind]} · ${record.topic.category}`), make('h2', record.hook), make('p', text.length > 230 ? `${text.slice(0, 230)}…` : text), open);
      list.append(card);
    });
    library.append(list);
  };
  const sync = () => {
    const state = studio.state();
    document.querySelector('[data-guest-saved-count]').textContent = String(state.saved.length);
    document.querySelector('[data-guest-draft-count]').textContent = String(Object.keys(state.drafts).length);
    links.forEach(link => {
      if (link.dataset.guestView === view) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    heading.textContent = views[view][0]; description.textContent = views[view][1];
    root.querySelector('.playground-body').hidden = view === 'drafts';
    root.querySelector('.topic-rail').hidden = view !== 'studio';
    library.hidden = view !== 'drafts';
    renderDrafts();
    history.replaceState(null, '', `#${view}`);
  };
  function navigate(name, focus = false) {
    view = views[name] ? name : 'studio';
    studio.chooseCollection(view === 'shortlist' ? 'saved' : 'all');
    sync();
    if (document.querySelector('[data-app-sidebar]').dataset.open === 'true') document.querySelector('[data-app-nav-close]').click();
    if (focus) { heading.focus({preventScroll: true}); window.scrollTo({top: 0, behavior: 'instant'}); }
  }
  links.forEach(link => link.addEventListener('click', event => { event.preventDefault(); navigate(link.dataset.guestView, true); }));
  root.addEventListener('markov:collection-change', () => {
    if (view !== 'drafts') view = studio.state().collection === 'saved' ? 'shortlist' : 'studio';
    sync();
  });
  window.addEventListener('hashchange', () => navigate(location.hash.slice(1)));
  document.querySelector('[data-guest-reset]').addEventListener('click', () => {
    if (document.querySelector('[data-app-sidebar]').dataset.open === 'true') document.querySelector('[data-app-nav-close]').click();
    resetDialog.showModal(); document.querySelector('[data-guest-reset-cancel]').focus();
  });
  document.querySelector('[data-guest-reset-cancel]').addEventListener('click', () => resetDialog.close());
  document.querySelector('[data-guest-reset-confirm]').addEventListener('click', () => {
    view = 'studio'; studio.reset(); resetDialog.close(); navigate('studio', true);
  });
  resetDialog.addEventListener('close', () => {
    if (document.querySelector('[data-app-sidebar]').inert) document.querySelector('[data-app-nav-open]').focus();
    else document.querySelector('[data-guest-reset]').focus();
  });
  navigate(view);
})();
