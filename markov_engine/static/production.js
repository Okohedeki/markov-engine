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
