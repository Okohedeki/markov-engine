(() => {
  'use strict';
  const topics = window.MarkovExamples || [];
  const root = document.querySelector('[data-idea-playground]');
  if (!root || !topics.length) return;
  const find = (selector) => root.querySelector(selector);
  const all = (selector) => [...root.querySelectorAll(selector)];
  const grid = find('[data-angle-grid]');
  const dialog = find('[data-idea-editor]');
  const draft = find('[data-idea-draft]');
  const format = find('[data-idea-format]');
  const status = find('[data-playground-status]');
  const editorStatus = find('[data-editor-status]');
  const records = topics.flatMap(topic => topic.angles.map((angle, index) => ({
    id: `${topic.id}-${index}`, topic, lens: angle[0], hook: angle[1], summary: angle[2], outline: angle[3]
  })));
  let selectedTopic = topics[0];
  let collection = 'all';
  let current = null;
  let saved = new Set();
  let edits = {};
  let savedDrafts = {};
  const kinds = ['post', 'thread', 'video'];
  const storageKey = root.dataset.storageKey || 'markov-creator-example-v1';
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
    saved = new Set(Array.isArray(stored.saved) ? stored.saved.filter(id => records.some(record => record.id === id)) : []);
    if (stored.edits && typeof stored.edits === 'object' && !Array.isArray(stored.edits)) edits = stored.edits;
    if (stored.drafts && typeof stored.drafts === 'object') {
      savedDrafts = Object.fromEntries(Object.entries(stored.drafts).filter(([id, kind]) => records.some(record => record.id === id) && kinds.includes(kind)));
    }
  } catch { status.textContent = 'Browser storage is unavailable. You can still explore and export this session.'; }
  const persist = () => {
    try {
      const retainedIds = new Set([...saved, ...Object.keys(savedDrafts)]);
      const retained = Object.fromEntries(Object.entries(edits).filter(([key, value]) => typeof value === 'string' && [...retainedIds].some(id => kinds.some(kind => key === `${id}:${kind}`))));
      localStorage.setItem(storageKey, JSON.stringify({saved: [...saved], edits: retained, drafts: savedDrafts}));
      return true;
    } catch { return false; }
  };
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const setSaved = (record, value) => {
    if (value) saved.add(record.id); else saved.delete(record.id);
    const stored = persist();
    status.textContent = `${value ? 'Added to' : 'Removed from'} your shortlist. ${stored ? 'Saved in this browser.' : 'Storage unavailable; export before leaving.'}`;
    render();
  };
  const textFor = (record, kind) => {
    const key = `${record.id}:${kind}`;
    if (typeof edits[key] === 'string') return edits[key];
    const points = record.outline.split('\n');
    if (kind === 'thread') return [record.hook, ...points, 'Your take: add a specific example or experience.'].map((text,i) => `${i + 1}/ ${text}`).join('\n\n');
    if (kind === 'video') return `HOOK\n${record.hook}\n\nSETUP\n${points[0]}\n\nDEVELOP\n${points.slice(1).join('\n')}\n\nCLOSE\nWhat should your audience do or think about next?`;
    return `${record.hook}\n\n${points.join('\n\n')}\n\nYour take: add a specific example or experience.`;
  };
  const openIdea = (record, kind = 'post') => {
    current = record;
    find('[data-editor-title]').textContent = record.hook;
    find('[data-editor-origin]').textContent = `${record.lens} · ${record.topic.category} · Example outline`;
    format.value = kinds.includes(kind) ? kind : 'post';
    draft.value = textFor(record, format.value);
    editorStatus.textContent = '';
    find('[data-save-idea]').textContent = saved.has(record.id) ? 'Save changes' : 'Save to shortlist +';
    dialog.showModal();
    find('[data-editor-close]').focus();
  };
  function render() {
    find('[data-mobile-topic]').value = selectedTopic.id;
    all('[data-topic]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.topic === selectedTopic.id)));
    all('[data-collection]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.collection === collection)));
    find('[data-topic-category]').textContent = collection === 'saved' ? 'Your collection' : selectedTopic.category;
    find('[data-topic-title]').textContent = collection === 'saved' ? 'A little less “what should I post?”' : selectedTopic.title;
    find('[data-topic-context]').textContent = collection === 'saved' ? 'Your saved example angles, across every conversation. Open any idea to develop it.' : selectedTopic.context;
    find('[data-saved-count]').textContent = String(saved.size);
    find('[data-angle-count]').textContent = String(selectedTopic.angles.length);
    find('[data-download]').disabled = saved.size === 0;
    const visible = records.filter(record => collection === 'saved' ? saved.has(record.id) : record.topic.id === selectedTopic.id);
    grid.replaceChildren();
    if (!visible.length) {
      const empty = element('div', undefined, 'playground-empty');
      empty.append(element('strong', 'Your next batch starts with one good idea.'), element('p', 'Explore the angles and tap + to collect the ones you want to post.'));
      grid.append(empty);
    }
    visible.forEach((record, index) => {
      const card = element('article', undefined, 'angle-card');
      const open = element('button');
      open.type = 'button';
      open.dataset.openIdea = record.id;
      open.setAttribute('aria-label', `Develop: ${record.hook}`);
      open.append(element('span', record.lens), element('h3', record.hook), element('p', record.summary, 'angle-summary'), element('small', 'Develop this idea ↗'));
      open.addEventListener('click', () => openIdea(record));
      const footer = element('footer');
      const toggle = element('button', saved.has(record.id) ? '✓' : '+');
      toggle.type = 'button';
      toggle.dataset.saveCard = record.id;
      toggle.setAttribute('aria-pressed', String(saved.has(record.id)));
      toggle.setAttribute('aria-label', `${saved.has(record.id) ? 'Remove' : 'Save'} idea: ${record.hook}`);
      toggle.addEventListener('click', () => {
        setSaved(record, !saved.has(record.id));
        (find(`[data-save-card="${record.id}"]`) || find('[data-collection="all"]')).focus();
      });
      footer.append(element('span', `Angle ${String(index + 1).padStart(2, '0')} · ${record.topic.category}`), toggle);
      card.append(open, footer);
      grid.append(card);
    });
    root.dispatchEvent(new CustomEvent('markov:collection-change'));
  }
  const chooseTopic = (id) => {
    selectedTopic = topics.find(topic => topic.id === id) || topics[0];
    collection = 'all';
    render();
    status.textContent = `Showing ${selectedTopic.angles.length} example angles about ${selectedTopic.category.toLowerCase()}.`;
  };
  all('[data-topic]').forEach(button => button.addEventListener('click', () => chooseTopic(button.dataset.topic)));
  find('[data-mobile-topic]').addEventListener('change', (event) => chooseTopic(event.target.value));
  all('[data-collection]').forEach(button => button.addEventListener('click', () => { collection = button.dataset.collection; render(); }));
  find('[data-editor-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    const draftTrigger = document.querySelector(`[data-guest-draft="${current?.id}"]`);
    (draftTrigger?.getClientRects().length ? draftTrigger : find(`[data-open-idea="${current?.id}"]`) || find('[data-collection="all"]')).focus();
  });
  draft.addEventListener('input', () => { edits[`${current.id}:${format.value}`] = draft.value; });
  format.addEventListener('change', () => { draft.value = textFor(current, format.value); editorStatus.textContent = `Showing the ${format.options[format.selectedIndex].text.toLowerCase()}.`; });
  find('[data-save-idea]').addEventListener('click', () => {
    edits[`${current.id}:${format.value}`] = draft.value;
    setSaved(current, true);
    editorStatus.textContent = status.textContent;
    find('[data-save-idea]').textContent = 'Save changes';
  });
  find('[data-save-draft]')?.addEventListener('click', () => {
    edits[`${current.id}:${format.value}`] = draft.value;
    savedDrafts[current.id] = format.value;
    const stored = persist();
    editorStatus.textContent = stored ? 'Draft saved in this browser. Find it in Your drafts.' : 'Draft kept for this session. Storage unavailable; copy or export before leaving.';
    render();
  });
  find('[data-copy-idea]').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(draft.value); editorStatus.textContent = 'Outline copied. Ready for your writing app.'; }
    catch { draft.focus(); draft.select(); editorStatus.textContent = 'Copy is unavailable here. The outline is selected so you can copy it manually.'; }
  });
  find('[data-download]').addEventListener('click', () => {
    const pieces = records.filter(record => saved.has(record.id)).map(record => {
      const drafts = ['post','thread','video'].filter(kind => typeof edits[`${record.id}:${kind}`] === 'string');
      return `## ${record.hook}\n\n${record.lens} · ${record.topic.category}\n\n${(drafts.length ? drafts : ['post']).map(kind => `### ${kind}\n\n${textFor(record, kind)}`).join('\n\n')}`;
    });
    const blob = new Blob([`# Markov shortlist\n\nPrewritten examples with your saved edits. Verify facts before publishing.\n\n${pieces.join('\n\n---\n\n')}\n`], {type:'text/markdown;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = element('a');
    link.href = url; link.download = 'markov-shortlist.md';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status.textContent = `Exported ${saved.size} shortlisted ideas.`;
  });
  // The guest shell uses the same editor and collection behavior as the example.
  root.markovPlayground = {
    state: () => ({records, topics, saved: [...saved], drafts: {...savedDrafts}, collection, selectedTopic, textFor}),
    chooseTopic,
    chooseCollection: (value) => { collection = value === 'saved' ? 'saved' : 'all'; render(); },
    open: (id, kind) => { const record = records.find(item => item.id === id); if (record) openIdea(record, kind); },
    reset: () => {
      saved = new Set(); edits = {}; savedDrafts = {}; collection = 'all'; selectedTopic = topics[0];
      const stored = persist(); render();
      status.textContent = stored ? 'Guest workspace reset. Your sample conversations are ready again.' : 'This session was reset. Browser storage is unavailable.';
    }
  };
  render();
})();
