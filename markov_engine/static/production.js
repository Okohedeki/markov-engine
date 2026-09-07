(() => {
  const form = document.querySelector('[data-batch-form]');
  if (!form) return;
  const boxes = [...form.querySelectorAll('input[name="item"]')];
  const all = form.querySelector('[data-select-all]');
  const count = form.querySelector('[data-selected-count]');
  const status = form.querySelector('[data-queue-status]');
  const paidButton = form.querySelector('[data-unit-cost]');
  all.hidden = false;
  all.setAttribute('aria-label', 'Select all stories on this page');
  const update = () => {
    const selected = boxes.filter(box => box.checked).length;
    count.textContent = selected ? `${selected} selected on this page` : 'Select this page';
    all.checked = selected > 0 && selected === boxes.length;
    all.indeterminate = selected > 0 && selected < boxes.length;
    if (paidButton) form.querySelector('[data-batch-cost]').textContent = selected
      ? `Up to ${selected * Number(paidButton.dataset.unitCost)} credits for ${selected} new talking-point outputs. Previously generated outputs are reused.`
      : `Select up to 30 ideas. New talking-point outputs use ${paidButton.dataset.unitCost} credits each.`;
  };
  all.addEventListener('change', () => { boxes.forEach(box => { box.checked = all.checked; }); update(); });
  boxes.forEach(box => box.addEventListener('change', update));
  form.addEventListener('submit', event => {
    const selected = boxes.filter(box => box.checked).length;
    const action = event.submitter?.value;
    if (!selected || (action === 'series' && selected < 2)) {
      event.preventDefault();
      status.textContent = action === 'series' ? 'Select at least two stories for a series.' : 'Select at least one story first.';
      (boxes[0] || all).focus();
      return;
    }
    status.textContent = action === 'talking_points' ? 'Developing your selection. Keep this page open; completed outputs will appear in Talking points.' : '';
    if (action === 'talking_points') {
      if (form.dataset.submitting) { event.preventDefault(); return; }
      form.dataset.submitting = 'true';
      event.submitter.setAttribute('aria-disabled', 'true');
    }
  });
  window.addEventListener('pageshow', () => { delete form.dataset.submitting; paidButton?.removeAttribute('aria-disabled'); update(); });
  update();
})();

(() => {
  const intake = document.getElementById('new-topic');
  if (!intake) return;
  const reveal = () => {
    intake.open = true;
    intake.querySelector('input[name="value"]')?.focus();
  };
  document.querySelectorAll('a[href="/app#new-topic"]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      history.replaceState(null, '', `${location.pathname}${location.search}#new-topic`);
      reveal();
    });
  });
  if (location.hash === '#new-topic') reveal();
  window.addEventListener('hashchange', () => {
    if (location.hash === '#new-topic') reveal();
  });
})();

// Read stored material only: opening a story never starts research or generation.
(() => {
  const queueLink = path => {
    const url = new URL(path, location.origin);
    url.searchParams.set('queue', location.search.slice(1));
    return url.pathname + url.search + url.hash;
  };
  document.querySelectorAll('.production-row a[href^="/app/artifacts/"]').forEach(link => {
    link.href = queueLink(link.getAttribute('href'));
  });
  const add = (parent, tag, text, className) => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    parent.append(node);
    return node;
  };
  document.querySelectorAll('[data-story-preview]').forEach(details => {
    const content = details.querySelector('[data-preview-content]');
    const load = async () => {
      if (!details.open || details.dataset.loaded || details.dataset.loading) return;
      details.dataset.loading = 'true';
      content.replaceChildren();
      add(content, 'p', 'Loading saved sources and documents…').setAttribute('role', 'status');
      content.setAttribute('aria-busy', 'true');
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetch(`/app/queue/preview?item=${encodeURIComponent(details.dataset.item)}`, {
          signal: controller.signal, headers: { Accept: 'application/json' }, cache: 'no-store',
        });
        if (!response.ok) throw new Error('Source preview unavailable');
        const data = await response.json();
        content.replaceChildren();
        add(content, 'p', data.angle, 'production-preview-angle');
        const packet = data.story_packet;
        add(content, 'p', packet ? packet.question : 'Collected for this topic, not proof of every story angle. Check the original passages before writing.', 'production-preview-note');
        if (packet) {
          add(content, 'p', `Why follow it: ${packet.why_it_matters || packet.novelty_basis}`);
          add(content, 'p', `Still unresolved: ${packet.uncertainty}`, 'production-preview-note');
          const evidence = add(content, 'details', '', 'production-evidence');
          add(evidence, 'summary', `Read retained passages · ${packet.findings.length}`);
          packet.findings.forEach(finding => {
            const challenge = (packet.challenge_evidence_ids || []).includes(finding.evidence_id);
            add(evidence, 'h4', `${challenge ? 'Challenge / context' : 'Supporting material'} · E${finding.evidence_id}`);
            add(evidence, 'blockquote', finding.passage);
            const source = add(evidence, 'a', `${finding.title} · ${finding.locator || 'Retained passage'} ↗`);
            const url = new URL(finding.url, location.origin);
            if (['http:', 'https:'].includes(url.protocol)) {
              source.href = url.href;
              source.target = '_blank';
              source.rel = 'noopener noreferrer';
            }
          });
        }
        const columns = add(content, 'div', '', 'production-preview-columns');
        const sources = add(columns, 'section', '');
        add(sources, 'h4', `Source material · ${data.source_count}`);
        const sourceList = add(sources, 'ul', '');
        data.sources.forEach(source => {
          const item = add(sourceList, 'li', '');
          const title = add(item, source.url ? 'a' : 'strong', source.title);
          if (source.url) {
            const url = new URL(source.url);
            if (['https:', 'http:'].includes(url.protocol)) {
              title.href = url.href;
              title.target = '_blank';
              title.rel = 'noopener noreferrer';
              title.setAttribute('aria-label', `${source.title} (opens in a new tab)`);
            }
          }
          add(item, 'small', `${source.host} · ${source.role.replaceAll('_', ' ')}`);
        });
        if (!data.sources.length) add(sources, 'p', 'No source material is attached yet.');
        if (data.source_count > data.sources.length) add(sources, 'p', 'Showing the first 12 sources. Open the full trail below for all material.');
        const documents = add(columns, 'section', '');
        add(documents, 'h4', 'Writing & research');
        add(documents, 'p', packet ? 'This story’s draft and the original research context.' : 'Saved documents for this topic.');
        const documentList = add(documents, 'ul', '');
        const labels = { script: 'Script / talking points', brief: 'Source brief', research_report: 'Research notes' };
        data.documents.forEach(doc => {
          const item = add(documentList, 'li', '');
          const link = add(item, 'a', labels[doc.type] || doc.type.replaceAll('_', ' '));
          link.href = queueLink(doc.url);
          add(item, 'small', `${doc.status.replaceAll('_', ' ')} · ${doc.title}`);
        });
        if (!data.documents.length) add(documents, 'p', `No saved document yet. Research status: ${data.research_status.replaceAll('_', ' ')}.`);
        details.dataset.loaded = 'true';
      } catch {
        content.replaceChildren();
        add(content, 'p', 'Could not load this story. Retry, or open the full source trail below.').setAttribute('role', 'status');
        const retry = add(content, 'button', 'Retry loading');
        retry.type = 'button';
        retry.addEventListener('click', load);
      } finally {
        clearTimeout(timeout);
        delete details.dataset.loading;
        content.removeAttribute('aria-busy');
      }
    };
    details.addEventListener('toggle', load);
  });
})();
