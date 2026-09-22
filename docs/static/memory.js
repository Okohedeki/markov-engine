/* Progressive enhancement: saves are acknowledged only after durable persistence. */
function initializeSaveDialog() {
  const dialog = document.getElementById('save-dialog');
  if (!dialog) return;
  let opener;
  const open = (trigger) => {
    opener = trigger;
    dialog.showModal();
    dialog.querySelector('[name="url"]').focus();
  };
  document.querySelectorAll('[data-open-save]').forEach(button => {
    button.addEventListener('click', () => open(button));
  });
  dialog.querySelector('[data-close-dialog]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => opener?.focus());
  const form = dialog.querySelector('form');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('[type="submit"]');
    const message = form.querySelector('[data-form-message]');
    const original = button.innerHTML;
    button.disabled = true;
    button.textContent = 'Saving…';
    message.textContent = '';
    try {
      const response = await fetch(form.action, {
        method: 'POST', body: new URLSearchParams(new FormData(form)),
        headers: {Accept: 'application/json'},
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Could not save. Please try again.');
      message.textContent = result.created ? 'Saved to Markov. You can close this now.' : 'Already in your library. Your existing thought is preserved.';
      button.textContent = 'Saved ✓';
      setTimeout(() => { window.location.assign(result.url + '?saved=1'); }, 900);
    } catch (error) {
      message.textContent = navigator.onLine ? error.message : 'You’re offline. Keep this window open and retry when connected.';
      button.disabled = false;
      button.innerHTML = original;
    }
  });
  const shared = new URLSearchParams(location.search);
  if (shared.has('save')) open(document.querySelector('[data-open-save]'));
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's' && !dialog.open) {
      event.preventDefault();
      open(document.querySelector('[data-open-save]'));
    }
  });
}
initializeSaveDialog();
